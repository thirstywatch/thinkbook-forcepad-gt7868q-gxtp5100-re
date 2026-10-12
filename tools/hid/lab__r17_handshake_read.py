#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r17_handshake_read.py —— 在 cfg_update 握手上下文里读 0x96F8

背景（第 16 轮 lab__r16_cfg_live_dump.py 的发现）：
  非握手状态下，0x96F8 起 256B 里只有前 32B 与容器 cfg 一致，其余全是
  "76xx/77xx" 形态的采样值，且 +0x100~0x11F 完全不可读（长度依赖、自相矛盾）。
  ⇒ 疑似 0x96F8 平时是【采样缓冲】，只在 cfg_update 会话期间才映射成【cfg 暂存区】。

本实验要回答的唯一问题：
  ★ 在官方 cfg_update 时序里（0x80 握手后、0x83 之前），0x96F8 读出来是不是真正的 cfg？

方法（幂等、零改动）：
  1) 走 0x80 → 等 0x82 握手
  2) 【T1】在写任何数据【之前】读 0x96F8 前 64B      <- 看握手后此地址变没变
  3) 写入【原样 cfg】（与 flash 逐字节相同 ⇒ 期望 7E 00 07）
  4) 【T2】在 0x83 之前再读 0x96F8 前 64B           <- 看写入后是否为 cfg
  5) 0x83 → 读结果 → 0x7D
  6) 【T3】结束后再读一次 0x96F8 前 64B              <- 看是否退回采样缓冲

★ 全程写入的是【与 flash 完全一致的原始 cfg】，不修改任何配置字节。
   预期结果码 7E 00 07（幂等），即"什么都没变"。
"""

import os
import sys
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lab__r13_cfgupdate import (  # noqa: E402
    Gx, cmd_init, write_chunked, poll_cmd, load_cfg,
    CFG_ADDR, CMD_ADDR, CFG_BODY_OFF, CFG_BODY_LEN, CHUNK, USE_CONT,
)

import time  # noqa: E402

IMAGE = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
NREAD = 64


def r64(g, label):
    """读 CFG_ADDR 起 NREAD 字节，返回 bytes|None"""
    d, _ = g.read(CFG_ADDR, NREAD, rounds=4, delay=0.05)
    if d:
        d = bytes(d)
        print("      %s (%dB) = %s" % (label, len(d), d.hex(" ")))
    else:
        print("      %s = <FAIL>" % label)
    return d


def prefix_match(a, b):
    if not a or not b:
        return 0
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def main():
    print("=" * 96)
    print("### 握手上下文里读 0x96F8 —— 判定它平时是【采样缓冲】还是会话期【cfg 暂存区】")
    print("=" * 96)

    cfg, same4, clen = load_cfg(IMAGE)
    print("  容器 cfg body：%d B（容器 %d B，4 副本相同=%s）sha256 = %s"
          % (len(cfg), clen, same4, hashlib.sha256(cfg).hexdigest()))
    print("  期望落地字节（写的就是它，未改动）：%s ..." % cfg[:32].hex(" "))
    print()

    g = Gx()
    if not g.open():
        print("  ✗ 无法打开 Col04")
        return 1
    print("  Col04 open ok")
    print()

    try:
        # ---- 基线：非握手态 ----
        print("  [0] 基线（非握手态）读 0x96F8")
        base = r64(g, "T0 基线")
        print()

        print("  [1] 读 cfg 版本 (0x96F8,3B)")
        before, _ = g.read(CFG_ADDR, 3)
        print("      before = %s" % (before.hex(" ") if before else "<FAIL>"))
        print()

        print("  [2] 等 IC 空闲：轮询 0x4160 == 0xFF")
        d, good = poll_cmd(g, 0xFF, tries=20, label="idle")
        print("      0x4160 = %s  %s" % (d.hex(" ") if d else "<FAIL>", "OK" if good else "超时"))
        print()

        print("  [3] 握手 0x80")
        g.write(CMD_ADDR, bytes(cmd_init(0x80, 0)))
        time.sleep(0.25)

        print("  [4] 等 IC 确认 0x82")
        d, good = poll_cmd(g, 0x82, tries=20)
        print("      0x4160 = %s  %s" % (d.hex(" ") if d else "<FAIL>",
                                          "确认 ✓" if good else "未确认 ✗"))
        if not good:
            print("  ✗ 未握手，中止（未写数据）")
            return 1
        print()

        # ★ T1：握手后、写入前
        print("  [5] ★ T1 —— 握手后、写数据【之前】读 0x96F8")
        t1 = r64(g, "T1 (握手后 未写)")
        print()

        # 写原样 cfg
        print("  [6] 写入【原样 cfg】（%d B，分 %d 块）—— 零改动"
              % (len(cfg), (len(cfg) + CHUNK - 1) // CHUNK))
        ok, done, total = write_chunked(g, CFG_ADDR, cfg, chunk=CHUNK, delay=0.03,
                                        verbose=False, advance=True, use_cont=USE_CONT)
        print("      写入 %s (%d/%d)" % ("成功" if ok else "失败", done, total))
        if not ok:
            print("  ✗ 写失败，中止")
            return 2
        time.sleep(0.10)
        print()

        # ★ T2：写入后、0x83 之前
        print("  [7] ★ T2 —— 写数据【之后】、0x83【之前】读 0x96F8")
        t2 = r64(g, "T2 (已写 未0x83)")
        print()

        print("  [8] 通知 IC 0x83")
        g.write(CMD_ADDR, bytes(cmd_init(0x83, 0)))
        time.sleep(0.08)

        print("  [9] 读校验结果 (0x4160, 5B)")
        res = None
        for _ in range(30):
            d, _ = g.read(CMD_ADDR, 5, rounds=4, delay=0.05)
            if d and len(d) >= 3 and d[0] in (0x7F, 0x7E):
                res = bytes(d)
                break
            time.sleep(0.03)
        if res:
            print("      结果 = %s" % res.hex(" "))
            if res[0] == 0x7E and res[1] == 0x00 and res[2] == 0x07:
                print("      ★★★ 7E 00 07 = 与 flash 完全一致（幂等，什么都没改）")
            elif res[0] == 0x7E:
                print("      7E 00 %02X%02X" % (res[1], res[2]))
            elif res[0] == 0x7F:
                print("      7F = 已接受并写入")
        else:
            print("      <FAIL>")
        print()

        print("  [10] 结束 0x7D")
        g.write(CMD_ADDR, bytes(cmd_init(0x7D, 0)))
        time.sleep(0.10)
        print()

        print("  [11] ★ T3 —— 会话结束后读 0x96F8")
        t3 = r64(g, "T3 (会话后)")
        print()

        print("=" * 96)
        print("### 判定")
        print("=" * 96)
        rows = [("T0 基线(非握手)", base), ("T1 握手后/未写", t1),
                ("T2 已写/未0x83", t2), ("T3 会话后", t3)]
        print("  与【容器 cfg】的前缀一致字节数：")
        for name, d in rows:
            if d is None:
                print("    %-18s : <读失败>" % name)
            else:
                n = prefix_match(d, cfg)
                print("    %-18s : %2d / %d 前%dB=%s"
                      % (name, n, len(d), min(16, len(d)), d[:16].hex(" ")))
        print()
        # 是否有 '76xx/77xx' 采样特征
        def sampling_like(d):
            if not d or len(d) < 8:
                return False
            pairs = sum(1 for i in range(0, len(d) - 1) if d[i] in (0x76, 0x77))
            return pairs >= len(d) // 4
        print("  是否呈【采样值特征】(76xx/77xx 密集)：")
        for name, d in rows:
            print("    %-18s : %s" % (name, "★ 是" if sampling_like(d) else "否"))
        print()
        print("=" * 96)
        print("★ 本工具写入的是原样 cfg（幂等），未修改任何配置字节。")
        print("=" * 96)
        return 0
    finally:
        g.close()


if __name__ == "__main__":
    sys.exit(main())
