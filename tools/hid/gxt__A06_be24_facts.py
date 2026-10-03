# -*- coding: utf-8 -*-
"""A6. 定案（终）：正确的字段抽取。
逐字节（12 项 @0x1164, 8B/项）：
  item0: 03 00 00 20 00 01 60 00
  item1: 03 00 00 20 00 00 60 00
  item7: 02 00 00 30 00 00 10 00
观察：
  b0 = type (03 或 02)
  b1 = 00 恒
  大小：item0..6,9 = 0x2000 ; item7,10 = 0x3000 ; item8,11 = 0x1000
        -> 这些值 = bytes[1..3] 读成 be24 = 0x002000 / 0x003000 / 0x001000  ✓
        （因为 b1=00 恒，be24(b1,b2,b3) == be16(b2,b3) 但不重要）
  地址：item0 = 0x160, item1 = 0x060, item7 = 0x010, item11 = 0x120, item6 = 0x100
        -> 这些值 = bytes[4..6] 读成 be24 = 0x000160 / 0x000060 / 0x000010 / 0x000120 / 0x000100 ✓
        （b4=00 恒）
  b7 = 00 恒
=> 记录 = [type:u8][size:be24][addr:be24][pad:u8]  → 但 b1,b4 是 be24 的高字节，恒 0，等于被拆成 u16.

关键：地址的真实数值 0x60、0x80、0xA0 …… 是 **以 0x1000 为单位的页号**吗？
  0x160*0x1000 = 0x160000 > 文件长，不自洽。
  但 0x60 页 * 0x1000 = 0x60000 也超长。
=> 所以 addr 字段本身不是页号，需要再乘/再加。下面用机器判定。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW); T = 0x1164

# 从逐字节事实出发，抽取 (type, size, addr) 三个整数
recs = []
for i in range(12):
    o = T + i*8
    t  = FW[o]
    sz = (FW[o+1] << 16) | (FW[o+2] << 8) | FW[o+3]     # be24
    ad = (FW[o+4] << 16) | (FW[o+5] << 8) | FW[o+6]     # be24
    pad= FW[o+7]
    recs.append((i, t, sz, ad, pad))

print("=" * 84)
print("A6. 从逐字节事实抽取 be24 字段")
print("=" * 84)
print(f"{'#':>3} {'type':>5} {'size(be24)':>12} {'addr(be24)':>12} {'pad':>4}")
for i,t,sz,ad,p in recs:
    print(f"{i:>3}   0x{t:02X}  0x{sz:06X}={sz:>6d}  0x{ad:06X}={ad:>6d}  0x{p:02X}")
print(f"\n  size 总和 = {sum(r[2] for r in recs)} = 0x{sum(r[2] for r in recs):X}")
print(f"  文件长度  = {N} = 0x{N:X}")

print("\n----- 检验: addr 字段是否等于 '以 0x1000 计数的页号' 的某种编码 -----")
for name, fn in [("addr*0x1000", lambda a: a*0x1000),
                 ("addr*0x100",  lambda a: a*0x100),
                 ("addr*0x200",  lambda a: a*0x200),
                 ("addr",        lambda a: a)]:
    vals = [fn(r[3]) for r in recs]
    mx = max(v+s for v,s in zip(vals,[r[2] for r in recs]))
    al = sum(1 for v in vals if v % 0x1000 == 0)
    print(f"  {name:12s} max_end=0x{mx:08X}  对齐数={al}/12")

print("\n----- ★ 关键检验：size 总和(0x18000=98304) 是否是文件长的'粒度对齐后'值？ -----")
print(f"  98304 / 161628 = {98304/161628:.4f}")
print(f"  161628 = 0x2775C;  98304 = 0x18000;  差值 = 0xF75C = {63324}")
print(f"  0x2775C 向上取整到 0x1000 = 0x28000 = 163840")
print(f"  98304 vs 163840 比值 = {98304/163840:.4f}  <- 不是简单取整关系")
