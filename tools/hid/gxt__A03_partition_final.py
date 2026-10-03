# -*- coding: utf-8 -*-
"""A3. 最终分区表结构判定。
原始字节（8B/项）:
  03000020 00016000
  ^^ type=0x03
    ^^^^^^ size = 0x002000 (be24)
          ^^^^ addr = 0x0160 (be16)
              ^^ flags = 0x00
标定：解出的 addr 必须覆盖整个 161628 B 文件，且不重叠、无荒谬值。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *

FW = load(); N = len(FW); T = 0x1164
print("=" * 78); print("A3. 分区表结构判定 (type:u8 + size:be24 + addr:be16 + flags:u8)"); print("=" * 78)

items = []
for i in range(12):
    o = T + i * 8
    t = FW[o]
    sz = (FW[o+1] << 16) | (FW[o+2] << 8) | FW[o+3]
    ad = (FW[o+4] << 8) | FW[o+5]
    fl = FW[o+6] | (FW[o+7] << 8)
    items.append((i, t, sz, ad, fl))

print(f"{'#':>3} {'fileoff':>8} {'type':>5} {'size':>8} {'addr':>7} {'flags':>6}   区间")
tot = 0
for i, t, sz, ad, fl in items:
    print(f"{i:>3}   0x{T+i*8:05X}   0x{t:02X} {sz:>8d} 0x{ad:05X} 0x{fl:04X}   "
          f"[0x{ad:05X}, 0x{ad+sz:05X})")
    tot += sz

print(f"\n  size 总和   = {tot} = 0x{tot:X}")
print(f"  文件长度    = {N} = 0x{N:X}")
print(f"  差值        = {N-tot} = 0x{N-tot:X}     <- 必须为 0 才说明覆盖完整")

print("\n----- 自洽检验 (结论A 声称的四项) -----")
print(f"  1) addr 0x1000 对齐 : {sum(1 for _,_,_,a,_ in items if a % 0x1000 == 0)}/12"
      f"   [原始 addr: {[hex(a) for _,_,_,a,_ in items]}]")
print(f"  2) size 0x1000 倍数 : {sum(1 for _,_,s,_,_ in items if s % 0x1000 == 0)}/12")
print(f"  3) 重叠             : ", end="")
segs = sorted((a, s, t) for _, t, s, a, _ in items)
ov = 0
for i in range(1, 12):
    if segs[i][0] < segs[i-1][0] + segs[i-1][1]:
        ov += 1
        print(f"\n       !! 重叠 [{segs[i-1][0]:#x},+{segs[i-1][1]:#x}) "
              f"vs [{segs[i][0]:#x},+{segs[i][1]:#x})", end="")
print(f" {ov}/11   -> {'无重叠' if ov==0 else '有重叠'}")

print("\n----- 区块布局图 (按 flash addr) -----")
prev = 0; gap_total = 0
for a, s, t in segs:
    if a > prev:
        g = a - prev
        gap_total += g
        print(f"  [空隙] 0x{prev:05X} - 0x{a:05X}  ({g} B)")
    print(f"  [type=0x{t:02X}] 0x{a:05X} - 0x{a+s:05X}  ({s:>6d} B)")
    prev = a + s
if prev < N:
    print(f"  [空隙] 0x{prev:05X} - 0x{N:05X}  ({N-prev} B)")
print(f"  空隙合计 = {gap_total} B")

print("\n----- 唯一性 & 其它结构假设的证伪 -----")
print("  A) 同一 96B 表 needle 全文件命中数：", end="")
pat = FW[T:T+96]; c = 0; st = 0; hits=[]
while True:
    k = FW.find(pat, st)
    if k < 0: break
    c += 1; hits.append(k); st = k+1
print(f"{c} -> {[hex(h) for h in hits]}")
print("     (顺带验证 12B/24B/48B/64B needle：)", end="")
for nl in (12, 24, 48, 64):
    p = FW[T:T+nl]; cc=0; s2=0
    while True:
        k = FW.find(p, s2)
        if k<0: break
        cc+=1; s2=k+1
    print(f"{nl}B={cc}", end="  ")
print()

print("\n  B) 证伪 '1 u8 + 2xBE32' 解读（原分析者的解读）：")
for i in range(12):
    o = T + i*8
    sz32 = be32(FW, o+1); ad32 = be32(FW, o+5)
    print(f"     [{i:2d}] size32=0x{sz32:08X} addr32=0x{ad32:08X}  "
          f"addr32%4096={ad32%4096}  -> {'对齐' if ad32%4096==0 else '未对齐'}")

print("\n  C) 用 '解出 addr 必须全部落在文件内' 作为判据，扫所有同构 offset：")
found = []
for off in range(0, N - 96):
    ok = True; endmax = 0; segsl = []
    for i in range(12):
        o = off + i*8
        if o+8 > N: ok=False; break
        t = FW[o]; sz = (FW[o+1]<<16)|(FW[o+2]<<8)|FW[o+3]
        ad = (FW[o+4]<<8)|FW[o+5]
        segsl.append((ad, sz))
        endmax = max(endmax, ad+sz)
    if not ok: continue
    if endmax == N and all(sz % 0x1000 == 0 and sz > 0 for _, sz in segsl):
        found.append(off)
print(f"     满足(end_max==文件长, size全为0x1000倍数, size>0) 的 offset = {found}")
