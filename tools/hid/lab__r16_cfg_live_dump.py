#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r16_cfg_live_dump.py —— 活体 cfg 区 vs 容器 cfg body 逐字节对齐

目的（纯只读，零风险）：
  上一轮发现 0x96F8+0x100~0x11F 在活体上"长度依赖、读数自相矛盾"（不可读）。
  而 cfg+0x10F/+0x111/+0x113/+0x115/+0x117/+0x119 六个字段全部落在那一段。
  ⇒ 必须先回答：活体那一段到底是什么？活体 cfg 与容器 cfg body 是否逐字节对齐？

方法：
  1) 用 gxmem.py 的 0x0E 20 读通道，dump 活体 0x96F8 起 N 字节（逐 16B 步进，只取 len=16 的真读数）
  2) 从容器 .BIN 里按 CFG_BODY_OFF=0x4C 定位 cfg body
  3) 逐字节比对，标出【相同 / 不同 / 活体为零 / 不可读】四类
  4) 输出 16B 行宽的双栏对照表

用法：
  python lab__r16_cfg_live_dump.py [--len 256] [--csv out.csv]
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
PYEXE = sys.executable
GXMEM = os.path.join(HERE, "gxmem.py")

IMAGE = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
CFG_BODY_OFF = 0x4C
CFG_BODY_LEN = 1084            # 1024 body + 60 tail
LIVE_BASE = 0x96F8


def live_read16(addr, size=16):
    """走 gxmem.py read，返回 (bytes|None, raw_line)"""
    r = subprocess.run([PYEXE, GXMEM, "read", hex(addr), str(size)],
                       capture_output=True, text=True, cwd=HERE)
    for line in r.stdout.splitlines():
        if "->" in line:
            hexpart = line.split("->")[1].strip()
            toks = [t for t in hexpart.split(" ") if t]
            try:
                data = bytes(int(t, 16) for t in toks)
            except ValueError:
                return None, line
            log = line.split("log=")[-1] if "log=" in line else ""
            return data, log
    return None, "(no output)"


def dump_live(nbytes):
    """逐 16B 读。若 len=16 返回全零，再用 len=8/4 探测该处是否真的不可读。"""
    out = []
    for off in range(0, nbytes, 16):
        addr = LIVE_BASE + off
        d16, log16 = live_read16(addr, 16)
        rec = {"off": off, "addr": addr, "d16": d16, "log16": log16,
               "probe": None, "readable": True}
        if d16 is None:
            rec["readable"] = False
        else:
            # 一致性检验：换长度读，看是否前缀一致
            d4, _ = live_read16(addr, 4)
            d8, _ = live_read16(addr, 8)
            if d4 is not None and d8 is not None and d16 is not None:
                ok = (d16[:4] == d4) and (d16[:8] == d8)
                rec["readable"] = ok
                rec["probe"] = (d4, d8)
            else:
                rec["readable"] = False
        out.append(rec)
    return out


def load_container():
    with open(IMAGE, "rb") as f:
        raw = f.read()
    # 定位 cfg body：容器里 4 份副本，第一份在 CFG_BODY_OFF（裸容器口径）
    body = raw[CFG_BODY_OFF:CFG_BODY_OFF + CFG_BODY_LEN]
    # 校验：4 副本
    copies = []
    for k in range(4):
        st = CFG_BODY_OFF + k * CFG_BODY_LEN
        copies.append(raw[st:st + CFG_BODY_LEN])
    identical = all(c == copies[0] for c in copies)
    return raw, body, identical, copies


def classify(live, cont):
    """返回每字节的标记：'=' 相同 / 'X' 不同 / '.' 活体不可读 / '0' 活体为 0 而容器非 0"""
    tags = []
    for i in range(len(live)):
        if i >= len(cont):
            tags.append("?")
            continue
        if live[i] == cont[i]:
            tags.append("=")
        elif live[i] == 0:
            tags.append("0")
        else:
            tags.append("X")
    return tags


def main():
    nbytes = 256
    csv_out = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--len" and i + 1 < len(args):
            nbytes = int(args[i + 1])
        if a == "--csv" and i + 1 < len(args):
            csv_out = args[i + 1]

    print("=" * 96)
    print("### 活体 cfg vs 容器 cfg body 逐字节对齐（纯只读）")
    print("=" * 96)
    print("  容器 : %s" % IMAGE)
    raw, cont, identical, copies = load_container()
    print("  容器大小 %d B · CFG_BODY_OFF=0x%X · 4 副本相同 = %s"
          % (len(raw), CFG_BODY_OFF, identical))
    import hashlib
    print("  容器 sha256 = %s" % hashlib.sha256(raw).hexdigest())
    print("  活体 : 0x%04X 起 %d B（通道 0x0E 20 读）" % (LIVE_BASE, nbytes))
    print()

    recs = dump_live(nbytes)
    live = b"".join(r["d16"] if r["d16"] else bytes(16) for r in recs)
    tags = classify(live, cont)

    # 统计
    from collections import Counter
    cnt = Counter(tags)
    print("  逐字节分类： = 相同 %d · X 不同 %d · 0 活体为零 %d"
          % (cnt.get("=", 0), cnt.get("X", 0), cnt.get("0", 0)))
    print("  不可读的 16B 行（换长度读不一致）：")
    bad_rows = [r for r in recs if not r["readable"]]
    if not bad_rows:
        print("     （无）")
    for r in bad_rows:
        print("     +0x%03X (0x%04X)  16B=%s  4B=%s  8B=%s"
              % (r["off"], r["addr"],
                 (r["d16"].hex(" ") if r["d16"] else "None"),
                 (r["probe"][0].hex(" ") if r["probe"] else "-"),
                 (r["probe"][1].hex(" ") if r["probe"] else "-")))
    print()

    print("-" * 96)
    print("### 逐行对照（16B 行宽）")
    print("  列1 = 偏移(+0xNNN)  列2 = 活体  列3 = 容器  列4 = 标记")
    print("-" * 96)
    for off in range(0, nbytes, 16):
        lv = live[off:off + 16]
        cv = cont[off:off + 16]
        tg = "".join(tags[off:off + 16])
        mark = ""
        if off in (0x100, 0x110, 0x120):
            mark = "  <<< 分界"
        print("  +0x%03X | %-47s | %-47s | %s%s"
              % (off, lv.hex(" "), cv.hex(" "), tg, mark))

    print("-" * 96)
    print("### 六个字段所在行的详查")
    for f in (0x10F, 0x111, 0x113, 0x115, 0x117, 0x119):
        row = (f // 16) * 16
        r = next((x for x in recs if x["off"] == row), None)
        lv = live[row:row + 16]
        cv = cont[row:row + 16]
        print("  +0x%03X 在行 +0x%03X : 活体 %-36s | 容器 %-36s | 可读=%s"
              % (f, row, lv.hex(" "), cv.hex(" "),
                 "是" if (r and r["readable"]) else "★ 否"))
    print()
    print("=" * 96)
    print("★ 本工具全程只读：只发 0x0E 20 读命令，不写任何配置。")
    print("=" * 96)

    if csv_out:
        import csv
        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["offset", "live", "container", "tag"])
            for i in range(nbytes):
                w.writerow(["0x%03X" % i, "%02X" % live[i], "%02X" % cont[i], tags[i]])
        print("\n  CSV 已写出：%s" % csv_out)


if __name__ == "__main__":
    main()
