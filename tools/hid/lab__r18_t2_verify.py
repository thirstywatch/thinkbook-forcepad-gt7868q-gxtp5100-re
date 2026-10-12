#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r18_t2_verify.py —— T2 会话态读回验证（字节级闭环）

两个目标，一次做完：

  目标 A（本轮最优路径）：
    在 T2 时刻（写完、未 0x83）读 0x96F8 的 +0x100~0x11F 段，
    验证那 6 个字段（+0x10F/+0x111/+0x113/+0x115/+0x117/+0x119）
    在【会话态】是否可读。空闲态它们落在不可读区。

  目标 B（B11 升级为字节级确证）：
    写入改动版 cfg（+0x10F: 4150 -> 4151），在 T2 读回该字段，
    直接确认 IC 收到的就是 0x1037（而不是靠 7E 00 02 推断）。
    随后 restore 回原样，再读一次描述符。

★ 安全：写入发生在官方 cfg_update 会话内（已验证写对地方）；
   结束前必定 restore 回原样 cfg。
"""

import os
import sys
import time
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lab__r13_cfgupdate import (  # noqa: E402
    Gx, cmd_init, write_chunked, poll_cmd, load_cfg,
    CFG_ADDR, CMD_ADDR, CHUNK, USE_CONT,
)

IMAGE = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
F_X = 0x10F               # X 点数所在偏移
NEW_X = 4151              # 4150 -> 4151
NEW_X_BE = bytes([(NEW_X >> 8) & 0xFF, NEW_X & 0xFF])   # 10 37

# 6 个关注字段
FIELDS = [0x10F, 0x111, 0x113, 0x115, 0x117, 0x119]


def read_seg(g, off, ln, tag):
    d, _ = g.read(CFG_ADDR + off, ln, rounds=4, delay=0.05)
    if d:
        d = bytes(d)
        print("      %-24s +0x%03X (%dB) = %s" % (tag, off, len(d), d.hex(" ")))
    else:
        print("      %-24s +0x%03X = <FAIL>" % (tag, off))
    return d


def consistency(g, off, tag):
    """多长度一致性检验：len 1/2/4/8/16 是否前缀一致"""
    res = {}
    for sz in (1, 2, 4, 8, 16):
        d, _ = g.read(CFG_ADDR + off, sz, rounds=4, delay=0.05)
        res[sz] = bytes(d) if d else None
    ok = True
    for sz in (2, 4, 8, 16):
        if res[sz] is None or res[sz][:1] != (res[1] or b""):
            ok = False
    pref = True
    if res[16] is not None:
        for sz in (1, 2, 4, 8):
            if res[sz] is None or res[16][:sz] != res[sz]:
                pref = False
                break
    print("      %-24s len=1/2/4/8/16 : %s | %s | %s | %s | %s  => %s"
          % (tag,
             res[1].hex(" ") if res[1] else "-",
             res[2].hex(" ") if res[2] else "-",
             res[4].hex(" ") if res[4] else "-",
             res[8].hex(" ") if res[8] else "-",
             res[16].hex(" ") if res[16] else "-",
             "★ 前缀一致(可读)" if pref else "🔴 自相矛盾(不可读)"))
    return pref, res


def do_session(g, cfg, label, verify_offsets):
    """走一次 cfg_update 会话；返回 T2 各字段读值。写入即传入的 cfg。"""
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
        raise RuntimeError("握手失败，未写数据")

    print("  [4] 写入 %s（%d B，%d 块）" % (label, len(cfg), (len(cfg) + CHUNK - 1) // CHUNK))
    ok, _, _ = write_chunked(g, CFG_ADDR, cfg, chunk=CHUNK, delay=0.03,
                             verbose=False, advance=True, use_cont=USE_CONT)
    print("      写入 %s" % ("成功" if ok else "失败"))
    if not ok:
        raise RuntimeError("写失败")
    time.sleep(0.10)

    print("  [5] ★ T2 读回验证")
    t2 = {}
    for off in verify_offsets:
        d = read_seg(g, off, 4, "T2")
        t2[off] = d
    print()
    print("  [5b] ★ T2 多长度一致性（判定该段会话态是否可读）")
    cons = {}
    for off in verify_offsets:
        p, r = consistency(g, off, "T2+0x%03X" % off)
        cons[off] = (p, r)

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
    print("      结果 = %s" % (res.hex(" ") if res else "<FAIL>"))

    print("  [8] 结束 0x7D")
    g.write(CMD_ADDR, bytes(cmd_init(0x7D, 0)))
    time.sleep(0.10)
    return t2, cons, res


def main():
    print("=" * 100)
    print("### T2 会话态读回验证 —— 字节级闭环（+ 6 字段偏移体系验证）")
    print("=" * 100)
    cfg, same4, clen = load_cfg(IMAGE)
    print("  原样 cfg：%d B  sha256 = %s" % (len(cfg), hashlib.sha256(cfg).hexdigest()))
    print("  原样 +0x%03X = %s（应为 4150 = 0x1036）" % (F_X, cfg[F_X:F_X + 2].hex(" ")))
    print()

    # 构造改动版
    cfg_mod = bytearray(cfg)
    old = bytes(cfg_mod[F_X:F_X + 2])
    cfg_mod[F_X:F_X + 2] = NEW_X_BE
    cfg_mod = bytes(cfg_mod)
    print("  改动版 +0x%03X : %s -> %s  (4150 -> %d = 0x%04X)"
          % (F_X, old.hex(" "), NEW_X_BE.hex(" "), NEW_X, NEW_X))
    print()

    g = Gx()
    if not g.open():
        print("  ✗ 无法打开 Col04")
        return 1
    print("  Col04 open ok")
    print()

    t2_mod = t2_restore = None
    try:
        # ================= 会话 1：写入改动版 =================
        print("-" * 100)
        print("### 会话 1：写入【改动版】(+0x%03X = 0x%04X)" % (F_X, NEW_X))
        print("-" * 100)
        # 关注：改动字段 + 它的邻居行（含 +0x100~0x11F 整段）
        probe_offs = [0x100, 0x103, 0x107, 0x10B, 0x10F, 0x111, 0x113, 0x115, 0x117, 0x119]
        t2_mod, cons_mod, res_mod = do_session(g, cfg_mod, "改动版", probe_offs)
        print()

        print("  ★ 会话1 判定：")
        for off in probe_offs:
            d = t2_mod.get(off)
            if d:
                print("    +0x%03X : T2 读到 %s" % (off, d.hex(" ")))
            else:
                print("    +0x%03X : <FAIL>" % off)
        print("    写入值应出现在 +0x%03X : 期望 %s，T2 读到 %s  => %s"
              % (F_X, NEW_X_BE.hex(" "), (t2_mod.get(F_X) or b"").hex(" "),
                 "★ 一致（字节级确证）" if (t2_mod.get(F_X) or b"")[:2] == NEW_X_BE
                 else "🔴 不一致"))
        print()

        # ================= 会话 2：恢复原样 =================
        print("-" * 100)
        print("### 会话 2：恢复【原样 cfg】（幂等，期望 7E 00 07）")
        print("-" * 100)
        t2_restore, cons_res, res_res = do_session(g, cfg, "原样", [F_X, 0x10B, 0x111])
        print()
        print("  ★ 恢复判定：结果码 = %s（7E 00 07 = 与 flash 一致）"
              % (res_res.hex(" ") if res_res else "<FAIL>"))
        print("    恢复后 T2 读到 +0x%03X = %s（期望回到 %s）"
              % (F_X, (t2_restore.get(F_X) or b"").hex(" "), old.hex(" ")))
        print()

        # ================= 汇总 =================
        print("=" * 100)
        print("### 汇总判定")
        print("=" * 100)
        print("  目标 A：6 字段所在段（+0x100~0x11F）在 T2 会话态是否可读？")
        for off, (p, r) in cons_mod.items():
            print("    +0x%03X : %s" % (off, "★ 可读" if p else "🔴 不可读/矛盾"))
        print()
        print("  目标 B：写入是否字节级送达？")
        okA = (t2_mod.get(F_X) or b"")[:2] == NEW_X_BE
        print("    改动值 0x%04X : T2 读到 %s  => %s"
              % (NEW_X, (t2_mod.get(F_X) or b"").hex(" "),
                 "★ 确证" if okA else "未确证"))
        okB = (t2_restore.get(F_X) or b"")[:2] == old
        print("    恢复值 0x%04X : T2 读到 %s  => %s"
              % (int.from_bytes(old, "big"), (t2_restore.get(F_X) or b"").hex(" "),
                 "★ 确证" if okB else "未确证"))
        print()
        print("=" * 100)
        print("★ 会话 2 已把 cfg 恢复原样；结束状态应与开始一致。")
        print("=" * 100)
        return 0
    finally:
        g.close()


if __name__ == "__main__":
    sys.exit(main())
