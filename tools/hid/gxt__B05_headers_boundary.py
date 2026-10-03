# -*- coding: utf-8 -*-
"""B05. 文件头 & 代码段入口 逐字节勘查。
观察: 0x00200/0x00600/0x00A00/0x00B00/0x00E00/0x00F00 非法率=0.0000 => 这些是 00/低熵填充。
     而 0x00000-0x00100 非法率=0.1969 => 有真实结构。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW)

print("=" * 92)
print("B05-a. 文件头 0x0000 - 0x0200")
print("=" * 92)
for o in range(0, 0x200, 16):
    print(f"  0x{o:05X}  {' '.join(f'{b:02x}' for b in FW[o:o+16])}"
          f"   {'...'.join(chr(b) if 32<=b<127 else '.' for b in FW[o:o+16])}")

print("\n" + "=" * 92)
print("B05-b. 各区段首个非零/低熵分布统计")
print("=" * 92)
def seg_stats(tag, off, ln):
    b = FW[off:off+ln]
    nz = sum(1 for x in b if x != 0)
    f0 = b.count(0)/len(b)
    ff = b.count(0xff)/len(b)
    print(f"  {tag:14s} 长度={len(b):>6d}  零字节占比={f0:.4f}  FF占比={ff:.4f}  非零={nz}")
for tag, off, ln in [("0x00000+256", 0x100, 0x100), ("0x00200", 0x200, 0x400),
                     ("0x00600", 0x600, 0x200), ("0x00A00", 0xa00, 0x200),
                     ("0x00C00", 0xc00, 0x200), ("0x01000", 0x1000, 0x200),
                     ("0x01200", 0x1200, 0x200), ("0x02000", 0x2000, 0x2000),
                     ("0x10000", 0x10000, 0x2000), ("0x19000", 0x19000, 0x2000),
                     ("0x19A00", 0x19a00, 0x200), ("0x26000", 0x26000, 0x1000),
                     ("0x27000", 0x27000, 0x75C)]:
    seg_stats(tag, off, ln)

print("\n" + "=" * 92)
print("B05-c. ★ 尾区段边界精扫: 0x26000 前后哪一字节开始变差")
print("=" * 92)
from capstone import *
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
def br64(off):
    i = off; ok = 0; bad = 0
    while i < off + 64:
        got = None
        for ins in md.disasm(FW[i:i+16], i):
            got = ins; break
        if got is None: bad += 1; i += 2; continue
        ok += 1; i += got.size
    return bad/(ok+bad) if ok+bad else 0
prev = None
for off in range(0x25800, 0x26600, 16):
    r = br64(off)
    mark = ""
    if prev is not None and abs(r-prev) > 0.2: mark = "  <<< 跃变"
    prev = r
    if r > 0 or mark:
        print(f"  0x{off:05X} bad={r:.4f}{mark}")

print("\n" + "=" * 92)
print("B05-d. 代码段真正起点: 逐 16B 扫 0x19800-0x19B00")
print("=" * 92)
for off in range(0x19800, 0x19B00, 16):
    r = br64(off)
    print(f"  0x{off:05X} bad={r:.4f} {'#'*int(r*40)}")
