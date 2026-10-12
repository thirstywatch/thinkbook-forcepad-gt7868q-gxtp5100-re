#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r21_persistence_test.py —— cfg 写入的【持久性】分层测试

背景（第 20 轮重启实验的意外发现）：
  写 +0x10F=4151 → 结果码 7E 00 02（"与 flash 不同"）
  → 重启设备 → 描述符不变(4149) → 再读 IC 里的值 = 10 36 (4150) = 原值
  ⇒ 改动【没有跨重启保持】，怀疑 7E 00 02 只代表"RAM 暂存区已改写"，≠ "已进 flash"

本实验把它拆成三层，逐层验证：

  层 1 · 同会话内（T2 时刻）读回        → 验证"RAM 暂存区是否被改写"
  层 2 · 关闭会话后、重新开会话读回      → 验证"是否已从暂存区落到别处"
  层 3 · 加 0x34/0x33 等收尾命令、再读   → 验证是否有"提交/落盘"命令

★ 测试字段用 +0x10F（X 点数），改 4150 -> 4151（差 1，无风险）
★ 每轮结束都 restore 回原样
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lab__r13_cfgupdate import (  # noqa: E402
    Gx, cmd_init, write_chunked, poll_cmd, load_cfg,
    CFG_ADDR, CMD_ADDR, CHUNK, USE_CONT,
)

IMAGE = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
F = 0x10F
ORIG = 4150
MOD = 4151


def session_write(g, cfg, label):
    """握手 + 写 + 返回 T2 读值（写完未 0x83）"""
    poll_cmd(g, 0xFF, tries=20)
    g.write(CMD_ADDR, bytes(cmd_init(0x80, 0)))
    time.sleep(0.25)
    d, good = poll_cmd(g, 0x82, tries=20)
    if not good:
        return None, "握手失败"
    ok, _, _ = write_chunked(g, CFG_ADDR, cfg, chunk=CHUNK, delay=0.03,
                             verbose=False, advance=True, use_cont=USE_CONT)
    if not ok:
        return None, "写失败"
    time.sleep(0.15)
    r, _ = g.read(CFG_ADDR + F, 2, rounds=4, delay=0.05)
    return (bytes(r) if r else None), None


def finish_session(g, extra_cmds=()):
    """0x83 -> 读结果 -> (可选额外命令) -> 0x7D，返回结果码"""
    g.write(CMD_ADDR, bytes(cmd_init(0x83, 0)))
    time.sleep(0.08)
    res = None
    for _ in range(30):
        d, _ = g.read(CMD_ADDR, 5, rounds=4, delay=0.05)
        if d and len(d) >= 3 and d[0] in (0x7F, 0x7E):
            res = bytes(d)
            break
        time.sleep(0.03)
    for c in extra_cmds:
        g.write(CMD_ADDR, bytes(cmd_init(c, 0)))
        time.sleep(0.15)
    g.write(CMD_ADDR, bytes(cmd_init(0x7D, 0)))
    time.sleep(0.15)
    return res


def session_peek(g, label):
    """全新会话：写原样，读 F 处的值（看"现在 IC 里是什么"）"""
    cfg, _, _ = load_cfg(IMAGE)
    t2, err = session_write(g, cfg, label)
    if err:
        print("      %s : %s" % (label, err))
        return None, None
    res = finish_session(g)
    return t2, res


def main():
    print("=" * 100)
    print("### cfg 写入持久性分层测试（+0x10F : 4150 -> 4151）")
    print("=" * 100)
    cfg, same4, clen = load_cfg(IMAGE)
    print("  原样 +0x%03X = %s" % (F, cfg[F:F + 2].hex(" ")))
    cfg_mod = bytearray(cfg)
    cfg_mod[F:F + 2] = bytes([(MOD >> 8) & 0xFF, MOD & 0xFF])
    cfg_mod = bytes(cfg_mod)
    print("  改动 +0x%03X = %s  (%d)" % (F, cfg_mod[F:F + 2].hex(" "), MOD))
    print()

    g = Gx()
    if not g.open():
        print("  ✗ 打开失败")
        return 1
    print("  Col04 open ok")
    print()
    try:
        # -------- 基线 --------
        print("-" * 100)
        print("### 层 0：基线 —— 当前 IC 里是什么")
        print("-" * 100)
        t2, res = session_peek(g, "基线")
        print("      T2 读 +0x%03X = %s   结果码 = %s"
              % (F, t2.hex(" ") if t2 else "FAIL", res.hex(" ") if res else "FAIL"))
        base = t2
        print()

        # -------- 层 1：同会话内写改动，T2 读回 --------
        print("-" * 100)
        print("### 层 1：同会话内写【改动】→ T2 读回（验证 RAM 暂存区被改写）")
        print("-" * 100)
        t2_mod, err = session_write(g, cfg_mod, "mod")
        if err:
            print("      %s" % err); return 2
        print("      T2 读 +0x%03X = %s  => %s"
              % (F, t2_mod.hex(" ") if t2_mod else "FAIL",
                 "★ RAM 暂存区已改" if t2_mod and t2_mod == cfg_mod[F:F + 2] else "未改"))
        res = finish_session(g)
        print("      结果码 = %s" % (res.hex(" ") if res else "FAIL"))
        print()

        # -------- 层 2：关会话后重新开会话读回 --------
        print("-" * 100)
        print("### 层 2：关闭会话 → 重新开会话 → 再读（验证是否落到别处）")
        print("-" * 100)
        t2, res = session_peek(g, "层2")
        print("      新会话 T2 读 +0x%03X = %s  => %s"
              % (F, t2.hex(" ") if t2 else "FAIL",
                 "★ 改动保留了（已落到别处）" if t2 and t2 == cfg_mod[F:F + 2]
                 else "🔴 已回原值（未保留）"))
        print("      结果码 = %s" % (res.hex(" ") if res else "FAIL"))
        print()

        # -------- 层 3：带 0x33/0x34 收尾再写一次 --------
        print("-" * 100)
        print("### 层 3：写【改动】+ 0x83 → 0x34 → 0x7D（试探是否有落盘命令）")
        print("-" * 100)
        poll_cmd(g, 0xFF, tries=20)
        g.write(CMD_ADDR, bytes(cmd_init(0x80, 0)))
        time.sleep(0.25)
        d, good = poll_cmd(g, 0x82, tries=20)
        if good:
            write_chunked(g, CFG_ADDR, cfg_mod, chunk=CHUNK, delay=0.03,
                          verbose=False, advance=True, use_cont=USE_CONT)
            time.sleep(0.15)
            t2b, _ = g.read(CFG_ADDR + F, 2, rounds=4, delay=0.05)
            print("      T2 读 = %s" % (bytes(t2b).hex(" ") if t2b else "FAIL"))
            res = finish_session(g, extra_cmds=[0x34])
            print("      结果码 = %s" % (res.hex(" ") if res else "FAIL"))
        print()
        t2, res = session_peek(g, "层3后")
        print("      新会话 T2 读 +0x%03X = %s  => %s"
              % (F, t2.hex(" ") if t2 else "FAIL",
                 "改动保留" if t2 and t2 == cfg_mod[F:F + 2] else "🔴 已回原值"))
        print()

        # -------- 收尾 restore --------
        print("-" * 100)
        print("### 收尾：restore 回原样")
        print("-" * 100)
        poll_cmd(g, 0xFF, tries=20)
        g.write(CMD_ADDR, bytes(cmd_init(0x80, 0)))
        time.sleep(0.25)
        d, good = poll_cmd(g, 0x82, tries=20)
        if good:
            write_chunked(g, CFG_ADDR, cfg, chunk=CHUNK, delay=0.03,
                          verbose=False, advance=True, use_cont=USE_CONT)
            time.sleep(0.15)
            res = finish_session(g)
            print("      restore 结果码 = %s  %s"
                  % (res.hex(" ") if res else "FAIL",
                     "（7E 00 07 = 与 flash 一致）" if res and res[:3] == b"\x7e\x00\x07" else ""))
        print()
        print("=" * 100)
        print("### 汇总结论")
        print("=" * 100)
        print("  基线   : %s" % (base.hex(" ") if base else "FAIL"))
        print("  层1    : %s  （T2 同会话）" % (t2_mod.hex(" ") if t2_mod else "FAIL"))
        print()
        print("  判读：若层1=10 37 而层2/层3 都=10 36 ⇒ **7E 00 02 只代表 RAM 被改写，未进 flash**")
        return 0
    finally:
        g.close()


if __name__ == "__main__":
    sys.exit(main())
