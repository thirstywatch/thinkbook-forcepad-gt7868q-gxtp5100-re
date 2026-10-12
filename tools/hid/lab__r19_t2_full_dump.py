#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r19_t2_full_dump.py —— T2 会话态全量 dump 1084B，与所发 cfg 逐字节 diff

要回答的问题：
  IC 在 T2 时刻（写完、未 0x83）持有的 1084 B，是否与我们发出去的**逐字节相同**？
  · 若完全相同 ⇒ IC 只是暂存，没有任何加工 ⇒ 差异源不在这里
  · 若有差异   ⇒ 差异位置 = 固件真正在意的字段（可能揭示"真源"）

方法：
  1) 走官方 cfg_update：0x80 → 等 0x82
  2) 写入【原样 cfg】（幂等，期望 7E 00 07）
  3) T2：从 0x96F8 起按 60B/次（读窗口上限）分块读满 1084 B
     —— 每次读用多长度一致性检验过滤"不可读"块
  4) 与所发 cfg diff，标出差异位置
  5) 0x83 → 读结果 → 0x7D

★ 写入的是原样 cfg，不改任何配置。
"""

import os
import sys
import time
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lab__r13_cfgupdate import (  # noqa: E402
    Gx, cmd_init, write_chunked, poll_cmd, load_cfg,
    CFG_ADDR, CMD_ADDR, CFG_BODY_LEN, CHUNK, USE_CONT,
)

IMAGE = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
READ_WINDOW = 60          # 单次读最大 60B（v2 回复恒 60B）


def read_block(g, off, ln):
    """读一块，并做多长度一致性校验。返回 (bytes|None, consistent)"""
    d, _ = g.read(CFG_ADDR + off, ln, rounds=4, delay=0.05)
    if not d:
        return None, False
    d = bytes(d)
    # 一致性：再读一次看是否稳定
    d2, _ = g.read(CFG_ADDR + off, ln, rounds=4, delay=0.05)
    d2 = bytes(d2) if d2 else None
    stable = (d2 == d)
    return d, stable


def main():
    print("=" * 100)
    print("### T2 会话态全量 dump —— IC 持有的 1084B vs 所发 cfg 逐字节 diff")
    print("=" * 100)
    cfg, same4, clen = load_cfg(IMAGE)
    print("  所发 cfg（原样）：%d B  sha256 = %s" % (len(cfg), hashlib.sha256(cfg).hexdigest()))
    print()

    g = Gx()
    if not g.open():
        print("  ✗ 无法打开 Col04")
        return 1
    print("  Col04 open ok")
    print()

    try:
        print("  [1] 等 IC 空闲 0x4160==0xFF")
        d, good = poll_cmd(g, 0xFF, tries=20)
        print("      0x4160 = %s  %s" % (d.hex(" ") if d else "<FAIL>", "OK" if good else "超时"))

        print("  [2] 握手 0x80")
        g.write(CMD_ADDR, bytes(cmd_init(0x80, 0)))
        time.sleep(0.25)

        print("  [3] 等确认 0x82")
        d, good = poll_cmd(g, 0x82, tries=20)
        print("      0x4160 = %s  %s" % (d.hex(" ") if d else "<FAIL>",
                                          "确认 ✓" if good else "未确认 ✗"))
        if not good:
            print("  ✗ 握手失败，未写数据")
            return 1

        print("  [4] 写入原样 cfg（%d B，%d 块）" % (len(cfg), (len(cfg) + CHUNK - 1) // CHUNK))
        ok, _, _ = write_chunked(g, CFG_ADDR, cfg, chunk=CHUNK, delay=0.03,
                                 verbose=False, advance=True, use_cont=USE_CONT)
        print("      写入 %s" % ("成功" if ok else "失败"))
        if not ok:
            return 2
        time.sleep(0.15)

        print("  [5] ★ T2 全量 dump 0x96F8 起 %d B（每次 %dB）" % (CFG_BODY_LEN, READ_WINDOW))
        got = bytearray()
        bad_blocks = []
        for off in range(0, CFG_BODY_LEN, READ_WINDOW):
            ln = min(READ_WINDOW, CFG_BODY_LEN - off)
            blk, stable = read_block(g, off, ln)
            if blk is None:
                print("      +0x%03X (%2dB) = <读失败>" % (off, ln))
                bad_blocks.append((off, ln, "FAIL"))
                got.extend(bytes(ln))
                continue
            # 长度可能不足（尾块）
            if len(blk) < ln:
                print("      +0x%03X (%2dB) = 只回 %dB  %s" % (off, ln, len(blk), blk.hex(" ")))
                bad_blocks.append((off, ln, "SHORT:%d" % len(blk)))
            else:
                mark = "" if stable else "  ⚠ 两次读不一致"
                if off % (READ_WINDOW * 2) == 0 or off >= CFG_BODY_LEN - READ_WINDOW:
                    print("      +0x%03X = %s%s" % (off, blk.hex(" "), mark))
                if not stable:
                    bad_blocks.append((off, ln, "UNSTABLE"))
            got.extend(blk[:ln])
        print()

        got = bytes(got)
        print("  [5b] dump 结果：%d B  sha256 = %s" % (len(got), hashlib.sha256(got).hexdigest()))
        print("       异常块：%s" % (bad_blocks if bad_blocks else "无"))
        print()

        # ---- diff ----
        print("-" * 100)
        print("### 逐字节 diff：IC 持有(T2) vs 所发 cfg")
        print("-" * 100)
        n = min(len(got), len(cfg))
        diffs = [(i, got[i], cfg[i]) for i in range(n) if got[i] != cfg[i]]
        same_count = n - len(diffs)
        print("  对齐长度 %d B ：相同 %d B · 不同 %d B" % (n, same_count, len(diffs)))
        print()
        if not diffs:
            print("  ★★★ 逐字节完全一致 —— IC 在 T2 时持有的就是我们所发的 1084 B，")
            print("      没有任何加工/校验注入。")
        else:
            print("  ★ 差异位置（偏移 · IC持有 · 所发）：")
            for i, a, b in diffs[:80]:
                print("    +0x%03X (%4d) : IC=%02X  所发=%02X" % (i, i, a, b))
            if len(diffs) > 80:
                print("    …共 %d 处" % len(diffs))
            print()
            # 差异是否集中在某段
            print("  差异分布（按 0x40 分桶）：")
            from collections import Counter
            buckets = Counter((i // 0x40) * 0x40 for i, _, _ in diffs)
            for b in sorted(buckets):
                print("    +0x%03X ~ +0x%03X : %d 处" % (b, b + 0x3F, buckets[b]))
        print()

        print("  [6] 通知 0x83")
        g.write(CMD_ADDR, bytes(cmd_init(0x83, 0)))
        time.sleep(0.08)

        print("  [7] 读校验结果")
        res = None
        for _ in range(30):
            d, _ = g.read(CMD_ADDR, 5, rounds=4, delay=0.05)
            if d and len(d) >= 3 and d[0] in (0x7F, 0x7E):
                res = bytes(d)
                break
            time.sleep(0.03)
        print("      结果 = %s  %s" % (res.hex(" ") if res else "<FAIL>",
                                      "（7E 00 07 = 与 flash 一致，幂等）"
                                      if res and res[:3] == b"\x7e\x00\x07" else ""))

        print("  [8] 结束 0x7D")
        g.write(CMD_ADDR, bytes(cmd_init(0x7D, 0)))
        time.sleep(0.10)
        print()
        print("=" * 100)
        print("★ 写入的是原样 cfg；会话 2 无需 restore（本次未做任何改动）。")
        print("=" * 100)
        return 0
    finally:
        g.close()


if __name__ == "__main__":
    sys.exit(main())
