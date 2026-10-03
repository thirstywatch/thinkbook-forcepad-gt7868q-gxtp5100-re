# -*- coding: utf-8 -*-
"""外层 4412 B（0x0000-0x113C）：结构 / 熵 / 是否含代码 / 4 条记录差异"""
import struct, collections, math, zlib, os
from capstone import *
d = open("bios-re/GT7868Q_native_fw.bin", 'rb').read()
W = d[0:0x113C]
def H(b):
    if not b: return 0
    c = collections.Counter(b); n = len(b)
    return -sum(v / n * math.log2(v / n) for v in c.values())
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
def thumb(b, lim=4096):
    off = ok = 0
    for ins in md.disasm(b[:lim], 0):
        if ins.address != off: break
        off += ins.size; ok += 1
    return ok * 2 / lim * 100
print("=== 外层总览 0x0000-0x113C (%d B) ===" % len(W))
print("H0=%.4f  zlib可压=%.4f  Thumb覆盖=%.1f%%" % (H(W), len(zlib.compress(W, 9)) / len(W), thumb(W)))
print("\n=== 4 条 1084 B 记录（自 0x10 起，步长 0x43C）===")
print("%-4s %-9s %-8s %-9s %-11s %-9s %s" % ("#", "file_off", "H0", "zlib", "两两相同", "Thumb%", "头部16B"))
recs = []
for r in range(4):
    p = 0x10 + r * 0x43C
    x = d[p:p + 0x43C]
    recs.append(x)
for r, x in enumerate(recs):
    same = ""
    if r: same = "%d/%d" % (sum(1 for a, b in zip(x, recs[0]) if a == b), len(x))
    print("%-4d 0x%06X  %-8.4f %-9.4f %-11s %-9.1f %s"
          % (r, 0x10 + r * 0x43C, H(x), len(zlib.compress(x, 9)) / len(x), same, thumb(x), x[:16].hex(' ')))
print("\n=== 1084 B 记录内部的字段（看是不是 TLV/表）===")
for r in [0, 1]:
    x = recs[r]
    print("  记录%d 前 96 B:" % r)
    for i in range(0, 96, 16):
        print("    +%03X  %-47s %s" % (i, " ".join("%02x" % c for c in x[i:i + 16]),
                                       "".join(chr(c) if 32 <= c < 127 else '.' for c in x[i:i + 16])))
print("\n=== 0x4C 处那段（与活体 0x96F8 明文相同）===")
seg = d[0x48:0x48 + 80]
for i in range(0, 80, 16):
    print("  +0x%03X  %-47s %s" % (0x48 + i, " ".join("%02x" % c for c in seg[i:i + 16]),
                                   "".join(chr(c) if 32 <= c < 127 else '.' for c in seg[i:i + 16])))
print("\n=== 逐字节：0x48 起 与 各记录中 0x3C 偏移处的对应 ===")
for r in range(4):
    p = 0x10 + r * 0x43C + 0x3C
    print("  记录%d +0x3C (abs 0x%06X): %s" % (r, p, d[p:p + 20].hex(' ')))
