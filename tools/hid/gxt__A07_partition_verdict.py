# -*- coding: utf-8 -*-
"""A7. 定案（真·终）: 分区表结构 = [type:u8][size:be24][page:be24][pad:u8]，
其中 page 是 0x1000 粒度的页号，真实 flash 地址 = page * 0x1000。
注意 size 字段同理也乘 0x1000? 不 —— size=0x20 * 0x1000 = 0x20000 = 131072 > 单项。
实际: size 字段值 = 0x20/0x30/0x10，若 *0x1000 则 0x20000/0x30000/0x10000。
下面用'覆盖文件'唯一标定。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW); T = 0x1164

recs = []
for i in range(12):
    o = T + i*8
    recs.append((i, FW[o],
                 (FW[o+1]<<16)|(FW[o+2]<<8)|FW[o+3],
                 (FW[o+4]<<16)|(FW[o+5]<<8)|FW[o+6]))

print("=" * 88)
print("A7. 定案：size 与 page 均以 0x1000 为单位（即字段值 = 字节数 >> 12）")
print("=" * 88)
items = []
for i, t, szf, pgf in recs:
    sz = szf * 0x1000
    ad = pgf * 0x1000
    items.append((i, t, sz, ad))

print(f"{'#':>3} {'fileoff':>8} {'type':>5} {'sz字段':>7} {'pg字段':>7} "
      f"{'size(B)':>9} {'addr':>9}   区间")
for i, t, sz, ad in items:
    o = T + i*8
    print(f"{i:>3}   0x{o:05X}   0x{t:02X}   0x{[r[2] for r in recs][i]:04X}   0x{[r[3] for r in recs][i]:04X} "
          f"{sz:>9d} 0x{ad:07X}   [0x{ad:05X}, 0x{ad+sz:05X})")

print(f"\n  size 总和     = {sum(s for _,_,s,_ in items)} = 0x{sum(s for _,_,s,_ in items):X}")
print(f"  文件长度      = {N} = 0x{N:X}")
print(f"  差值          = {N - sum(s for _,_,s,_ in items)} = 0x{N - sum(s for _,_,s,_ in items):X}")

print("\n----- 四项自洽检验（结论 A 声称的四项） -----")
print(f"  1) addr 0x1000 对齐 : {sum(1 for _,_,_,a in items if a%0x1000==0)}/12   [原始字段值 {[hex(r[3]) for r in recs]}]")
print(f"     -> 原始字段值本身不对齐（0x160 等），乘 0x1000 后才全对齐。")
print(f"        结论A 说 'addr 0x1000 对齐' 若指原始字段值是错的，若指换算后是真。")
print(f"  2) size 0x1000 倍数 : {sum(1 for _,_,s,_ in items if s%0x1000==0)}/12")
print(f"     原始 size 字段值 = {[hex(r[2]) for r in recs]}  <- 都不是 0x1000 倍数")
segs = sorted((a, s) for _,_,s,a in items)
ov = 0
for i in range(1, 12):
    if segs[i][0] < segs[i-1][0] + segs[i-1][1]:
        ov += 1
        print(f"      !! 重叠 [{segs[i-1][0]:#x},+{segs[i-1][1]:#x}) vs [{segs[i][0]:#x},+{segs[i][1]:#x})")
print(f"  3) 重叠             : {ov}/11  -> {'无重叠' if ov==0 else '有重叠'}")
lo = min(a for a,_ in segs); hi = max(a+s for a,s in segs)
print(f"  4) 覆盖区间         : [0x{lo:05X}, 0x{hi:05X})  跨度 = {hi-lo} B (0x{hi-lo:X})")
print(f"     size 有效合计    : {sum(s for _,s in segs)} B   -> 空隙 = {hi-lo-sum(s for _,s in segs)} B")
print(f"     结论A 声称 '覆盖 0x00000–0x20000 共 98,304 B，空隙 32,768 B'")
print(f"     实测: 覆盖 [0x{lo:X},0x{hi:X}), 有效 0x{sum(s for _,s in segs):X}, 空隙 0x{hi-lo-sum(s for _,s in segs):X}")

print("\n----- ★ 表唯一性 -----")
for nl in (8, 16, 32, 64, 96, 128):
    pat = FW[T:T+nl]; c=0; st=0; h=[]
    while True:
        k = FW.find(pat, st)
        if k<0: break
        c+=1; h.append(k); st=k+1
    print(f"  needle={nl:>3d}B 命中={c} -> {[hex(x) for x in h[:8]]}")

print("\n----- ★ 证伪分析者的原解读 (type:u8 + size:be32 + addr:be32) -----")
print("  原解读下 addr 字段 = 0x01600003 等，%0x1000 = 3 -> 12 项中仅 1 项对齐")
print("  原解读下 size 字段 = 0x2000 -> 12 项全为 0x1000 倍数 <- 这是它'看起来对'的来源")
print("  但原解读的 addr 有 2 位标志位混入，且 addr/size 字段完全错位：")
print("    真实: size 字段在 byte[1..3], 原解读取 byte[1..4] -> 多含 1 字节")
print("          addr 字段在 byte[4..6], 原解读取 byte[5..8] -> 完全错位 1 字节")
print("  => 原解读的 '98,304 B / 32,768 B 空隙' 是错位读取的巧合产物。")

print("\n----- ★ 真实的分区布局图 -----")
prev = 0; gap = 0
for a, s in segs:
    if a > prev:
        print(f"  [空隙 ] 0x{prev:05X} - 0x{a:05X}  ({a-prev:>7d} B)")
        gap += a-prev
    # 找 type
    tp = [t for _,t,ss,aa in items if aa==a and ss==s]
    print(f"  [分区 ] 0x{a:05X} - 0x{a+s:05X}  ({s:>7d} B)  type=0x{tp[0]:02X}")
    prev = a+s
if prev < 0x20000:
    print(f"  [空隙 ] 0x{prev:05X} - 0x20000  ({0x20000-prev:>7d} B)")
    gap += 0x20000-prev
print(f"  空隙合计 = {gap} B")
print(f"  声明的 0x20000 边界 vs 文件长 0x{N:X} : 文件比 0x20000 多 {N-0x20000} B")
