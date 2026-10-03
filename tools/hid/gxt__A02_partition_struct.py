# -*- coding: utf-8 -*-
"""A2. 分区表结构再判定：type(u8)+size(be16)+addr(be16)。
先用'必须覆盖 0x2775C'做标定 —— 只有正确解读才能让所有 end<=文件长。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *

FW = load(); N = len(FW)
T = 0x1164

print("=" * 78)
print("A2. 8B 表项结构判定 —— 用'能否覆盖整个文件'标定")
print("=" * 78)

def try_variant(es, ea, off=T, n=12):
    """t:u8 + size(endian es, 16bit) + addr(endian ea, 16bit)"""
    out = []
    for i in range(n):
        o = off + i * 8
        t = FW[o]
        sz = struct.unpack_from(es + "H", FW, o + 1)[0]
        ad = struct.unpack_from(ea + "H", FW, o + 3)[0]
        out.append((t, sz, ad))
    return out

for name, es, ea in [("BE16 size / BE16 addr", ">", ">"),
                     ("LE16 size / LE16 addr", "<", "<"),
                     ("BE16 size / LE16 addr", ">", "<"),
                     ("LE16 size / BE16 addr", "<", ">")]:
    its = try_variant(es, ea)
    maxend = max(a + s for _, s, a in its)
    over = sum(1 for _, s, a in its if a + s > N)
    segs = sorted((a, s) for _, s, a in its)
    ov = sum(1 for i in range(1, 12) if segs[i][0] < segs[i-1][0] + segs[i-1][1])
    cov = sum(s for _, s, _ in its)
    print(f"  {name:24s} max_end=0x{maxend:06X} 超文件={over} 重叠={ov} size总和=0x{cov:X}")

print("\n  >>> 判定：只有让 max_end == 文件长(0x2775C→需覆盖到 0x20000) 的解读才成立")
print("      注意 addr 高半字节 0x1000/0x2000 是页面基址，低半字节是标志位")

# 现在用正确解读展开
print("\n" + "=" * 78)
print("A2b. 正确解读下的 12 项分区表")
print("=" * 78)
print(f"{'#':>3} {'off':>7} {'type':>5} {'size':>7} {'addr':>7} {'flash页':>9} {'标志':>5}  {'区间':>18}")
items = []
for i in range(12):
    o = T + i * 8
    t = FW[o]
    sz = be16(FW, o + 1)
    ad = be16(FW, o + 3)
    page = ad & 0xF000
    flag = ad & 0x0FFF
    items.append((t, sz, ad, page, flag))
    print(f"{i:>3} 0x{o:05X}   0x{t:02X} {sz:>7d} 0x{ad:04X}  0x{page:05X}  0x{flag:03X}  "
          f"[0x{page:05X},0x{page+sz:05X})")

sizes = sorted((page, sz, t) for t, sz, ad, page, flag in items)
print("\n按 flash 地址排序：")
cov = 0
for a, s, t in sizes:
    print(f"  0x{a:05X} - 0x{a+s:05X}  size={s:>6d}  type=0x{t:02X}")
    cov += s
print(f"  size 总和 = {cov} = 0x{cov:X}   文件长 = {N} = 0x{N:X}")
print(f"  差值     = {N - cov}")

# 完整性：区间是否有空隙/重叠
print("\n覆盖完整性：")
prev_end = 0
gaps = []
for a, s, t in sorted(sizes):
    if a > prev_end:
        gaps.append((prev_end, a))
        print(f"  空隙: [0x{prev_end:05X}, 0x{a:05X})  = {a-prev_end} B")
    elif a < prev_end:
        print(f"  重叠: [0x{a:05X},0x{prev_end:05X})")
    prev_end = max(prev_end, a + s)
if prev_end < N:
    print(f"  尾部未覆盖: [0x{prev_end:05X}, 0x{N:05X}) = {N-prev_end} B")

# 唯一性：把整张表当 needle 再确认一次
print("\n" + "=" * 78)
print("A2c. 表唯一性 —— 用 96B 整表 needle（已在上一步验证，此处复核子串）")
print("=" * 78)
for nl in (8, 12, 16, 24, 48, 96):
    pat = FW[T:T+nl]
    cnt = 0; start = 0; hits=[]
    while True:
        k = FW.find(pat, start)
        if k < 0: break
        cnt += 1; hits.append(k); start = k + 1
    print(f"  needle={nl:>3d}B 命中={cnt} -> {[hex(x) for x in hits[:6]]}")

# 反向：8B 项里"size:B E16+addr:BE16"这个模式在文件里出现多少次
print("\n反查：合法的 8B 分区项模式 (type in 1..7, size%0x1000==0, size>0, page%0x1000==0)")
hits = []
for o in range(0, N - 8):
    t = FW[o]
    sz = be16(FW, o+1); ad = be16(FW, o+3)
    if 1 <= t <= 7 and sz and sz % 0x1000 == 0 and (ad & 0xF000) % 0x1000 == 0:
        hits.append(o)
print(f"  命中数={len(hits)}")
print(f"  offset 列表: {[hex(x) for x in hits[:40]]}")
# 连续成表的
print("\n  其中构成 >=3 项连续 8B 步长链的起点：")
best = []
i = 0
while i < len(hits):
    j = i
    while j+1 < len(hits) and hits[j+1] - hits[j] == 8:
        j += 1
    if j - i + 1 >= 3:
        best.append((hits[i], j - i + 1))
    i = j + 1
for off, n in best:
    print(f"    起点 0x{off:05X}  长度 {n} 项")
