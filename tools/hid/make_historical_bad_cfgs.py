#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_historical_bad_cfgs.py —— 确定性重建【历史 cfg 负例】+ 空闲态样本

为什么需要它（2026-10-14 整理轮发现）
------------------------------------------------
B36/B38 的结论建立在「三例对照」上：A 原样 / B 合法改写 / C 非法改写。
但仓库里**只留了 B**（tools/hid/_cfg_115_240_legal.bin），A 与 C 的实物都没入库：
  · 10 份 tools/hid/lab__cfg_backup_*.bin 经逐字节比对**全部等于基线**（只是原样读回，不是实验样本）
  · 历史上产生 7E 00 01 (PKGS_ERR) 的 _cfg_ver1C.bin 与产生 7E 00 02 (CHKSUM_ERR) 的非法改写件**都不在仓库**
=> 于是「负例不可复现」。本脚本用**纯离线**方式确定性重建它们：同样的输入 ⇒ 同样的字节 ⇒ 同样的 sha256。

生成物（默认写到 data/reference/）
------------------------------------------------
  lab__cfg_bad_bagnum_1C.bin        负例①：head[2] 0x1B→0x1C（袋数 27→28）+ 头校验随动
                                     ⇒ 第 28 袋起点 off=0x43C = 文件长度 ⇒ **越界**
                                     ⇒ 官方 TS_CFG_REPLY_PKGS_ERR = 0x01
  lab__cfg_bad_chksum_115_240.bin   负例②：+0x115 120→240，**袋尾不重算**（= 2026-10-05 r13 的历史原件）
                                     ⇒ 该袋 ys_ck != 0 ⇒ 官方 TS_CFG_REPLY_CHKSUM_ERR = 0x02
  lab__cfg_legal_115_240.bin        对照③：同一次改写 + **重算袋尾** ⇒ 27/27 合法
                                     （应与既有 _cfg_115_240_legal.bin 逐字节相同）
  lab__cfg_idle_phase_0x96F8_32B.bin 空闲态样本：从 tools/hid/_r62_log.txt 的 [restore] 行取 32 B（22 00 1B 00 3D …）

⚠️ 本脚本**不碰设备**：只读本地文件、只写本地文件。要验「IC 是否真的回 0x7E 00 01 / 0x7E 00 02」，
   需另跑 lab__r62_cfg_legal_write.py（真机、只写 0x96F8 会话 RAM）。

用法
------------------------------------------------
  python tools/hid/make_historical_bad_cfgs.py [--check] [--out DIR] [--base FILE]
      --check  只计算与校验，不写文件
"""
import sys, os, hashlib, argparse

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

PKGS_ERR = 0x01    # TS_CFG_REPLY_PKGS_ERR
CHKSUM_ERR = 0x02  # TS_CFG_REPLY_CHKSUM_ERR


def parse_bags(d):
    """按 §19.56 袋链语法解析：head 5 B + 重复 {u8 id, u8 len, data[len], u16 BE ck} bag_num 次。"""
    bag_num = d[2]
    bags, off = [], 5
    while len(bags) < bag_num and off + 4 <= len(d):
        bid, ln = d[off], d[off + 1]
        body_end = off + 2 + ln
        bags.append(dict(idx=len(bags), id=bid, off=off, len=ln, body_end=body_end))
        off = body_end + 2
    return bag_num, bags, off


def head_ck_ok(d):
    return ((d[3] << 8) | d[4]) == d[0] + d[1] + d[2]


def bag_ck(d, b):
    s = sum(d[b["off"]:b["body_end"]]) & 0xFFFF
    return s == ((d[b["body_end"]] << 8) | d[b["body_end"] + 1]), s


def rebuild_head_ck(d):
    ck = (d[0] + d[1] + d[2]) & 0xFFFF
    d[3], d[4] = (ck >> 8) & 0xFF, ck & 0xFF


def fix_bag_ck(d, b):
    """把该袋 2 B 校验尾重算为 sum(袋体)（官方 sum-to-zero 规则）。"""
    s = sum(d[b["off"]:b["body_end"]]) & 0xFFFF
    d[b["body_end"]], d[b["body_end"] + 1] = (s >> 8) & 0xFF, s & 0xFF


def report(tag, d, note):
    bag_num, bags, end = parse_bags(d)
    okc = sum(1 for b in bags if bag_ck(d, b)[0])
    end_note = "(=文件长度)" if end == len(d) else "(≠文件长度)"
    print("[%s] %d B  head_ck=%s  bag_num=%d  袋 %d/%d 通过  链末端=0x%X %s"
          % (tag, len(d), "OK" if head_ck_ok(d) else "BAD", bag_num, okc, len(bags), end, end_note))
    print("          " + note)
    print("          sha256=" + hashlib.sha256(bytes(d)).hexdigest())
    return bags


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    ap.add_argument("--base", default=os.path.join(root, "data", "reference", "lab__cfg_record_orig_1084.bin"))
    ap.add_argument("--out", default=os.path.join(root, "data", "reference"))
    ap.add_argument("--check", action="store_true", help="只计算，不写文件")
    a = ap.parse_args()

    base = bytearray(open(a.base, "rb").read())
    print("基线：%s  %d B" % (a.base, len(base)))
    report("基线", base, "期望：head_ck=OK · 27/27 通过 · 末端 = 文件长度")

    n, bags, _ = parse_bags(base)
    b6 = next((b for b in bags if b["off"] <= 0x115 < b["body_end"]), None)
    if b6 is None:
        print("!! +0x115 不在任何袋内，脚本假设变了，请复核")
        return 2
    print("       +0x115 落在 bag#%d (id=%d)，袋体 0x%X..0x%X" % (b6["idx"], b6["id"], b6["off"], b6["body_end"]))

    outs = {}

    # ---- 负例①：袋数越界 ----
    d1 = bytearray(base)
    d1[2] = 0x1C
    rebuild_head_ck(d1)
    n1, _, end1 = parse_bags(d1)
    outs["lab__cfg_bad_bagnum_1C.bin"] = d1
    report("负例① 袋数=0x1C", d1,
           "第 %d 袋起点 off=0x%X = %s ⇒ 官方 PKGS_ERR=0x%02X"
           % (n1, end1, "文件长度 ⇒ 越界" if end1 == len(d1) else "未越界", PKGS_ERR))

    # ---- 负例②：改数据不重算袋尾 ----
    d2 = bytearray(base)
    d2[0x115], d2[0x116] = 0x00, 0xF0   # 120 -> 240
    outs["lab__cfg_bad_chksum_115_240.bin"] = d2
    ok2, s2 = bag_ck(d2, b6)
    tail2 = (d2[b6["body_end"]] << 8) | d2[b6["body_end"] + 1]
    report("负例② 不重算袋尾", d2,
           "bag#%d 实际和=0x%04X vs 尾部=0x%04X ⇒ %s ⇒ 官方 CHKSUM_ERR=0x%02X"
           % (b6["idx"], s2, tail2, "仍通过" if ok2 else "校验失败", CHKSUM_ERR))

    # ---- 对照③：同样改写 + 重算袋尾 ----
    d3 = bytearray(d2)
    fix_bag_ck(d3, b6)
    outs["lab__cfg_legal_115_240.bin"] = d3
    report("对照③ 合法改写", d3, "期望：27/27 通过（= 既有 _cfg_115_240_legal.bin）")

    # ---- 空闲态样本（32 B 窗口）----
    logp = os.path.join(root, "tools", "hid", "_r62_log.txt")
    if os.path.exists(logp):
        for line in open(logp, encoding="utf-8", errors="replace"):
            if "0x96F8[0:32]" in line and "22 00 1B 00 3D" in line:
                idle = bytes(int(x, 16) for x in line.split("=", 1)[1].strip().split())
                outs["lab__cfg_idle_phase_0x96F8_32B.bin"] = bytearray(idle)
                print("[空闲态样本] %d B：%s … sha256=%s"
                      % (len(idle), idle[:5].hex(" ").upper(), hashlib.sha256(idle).hexdigest()))
                break
        else:
            print("[空闲态样本] !! 未能在 _r62_log.txt 找到 [restore] 行")
    else:
        print("[空闲态样本] !! 缺 %s" % logp)

    # ---- 与既有合法件交叉验证 ----
    ref = os.path.join(root, "tools", "hid", "_cfg_115_240_legal.bin")
    if os.path.exists(ref):
        same = bytes(d3) == open(ref, "rb").read()
        print("[交叉验证] 生成件 vs 既有 _cfg_115_240_legal.bin：%s" % ("逐字节相同 OK" if same else "不一致 !!"))

    if a.check:
        print()
        print("(--check：未写文件)")
        return 0

    os.makedirs(a.out, exist_ok=True)
    print()
    for name, data in outs.items():
        p = os.path.join(a.out, name)
        open(p, "wb").write(bytes(data))
        print("写出 %s  (%d B)" % (p, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
