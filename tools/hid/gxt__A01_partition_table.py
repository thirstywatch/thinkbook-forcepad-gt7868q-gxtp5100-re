# -*- coding: utf-8 -*-
"""A. 分区表复核
逐条验证：
  1. 表真的在 0x1164 吗？（这是"结论 A 声称的偏移"，必须先确认这个偏移怎么来的）
  2. 四项自洽检验（对齐/倍数/重叠/覆盖率）
  3. 表真的只有一份吗？用不同 needle 长度(8/16/32/64)全文件搜
  4. 8B 表项还有别的可能解读（LE size、LE addr、type 在前或在后）吗？逐一打分
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *

FW = load()
N = len(FW)
print("=" * 78)
print("A. 分区结构复核")
print("=" * 78)
print(f"文件长度 = {N} B = 0x{N:X}")

# ---------- A1. 先原样解析 0x1164 的 12 项 BE 表 ----------
print("\n----- A1. 原样解析 0x1164 (type:u8 + size:be32 + addr:be32) -----")
T = 0x1164
for i in range(12):
    o = T + i * 8
    t = FW[o]
    sz = be32(FW, o + 1)
    ad = be32(FW, o + 5)
    print(f"  [{i:2d}] @0x{o:05X}  type=0x{t:02X}  size=0x{sz:08X}({sz:>7d})  addr=0x{ad:08X}")

# ---------- A2. 四项自洽 ----------
print("\n----- A2. 自洽检验（按原样解读） -----")
items = []
for i in range(12):
    o = T + i * 8
    items.append((FW[o], be32(FW, o + 1), be32(FW, o + 5)))

al_ok = sum(1 for _, _, a in items if a % 0x1000 == 0)
sz_ok = sum(1 for _, s, _ in items if s % 0x1000 == 0)
print(f"  addr 0x1000 对齐 : {al_ok}/12")
print(f"  size 0x1000 倍数 : {sz_ok}/12")
segs = sorted([(a, s) for _, s, a in items if s > 0])
ov = 0
for i in range(1, len(segs)):
    if segs[i][0] < segs[i-1][0] + segs[i-1][1]:
        ov += 1
        print(f"    !! 重叠: [{segs[i-1][0]:#x},+{segs[i-1][1]:#x}) 与 [{segs[i][0]:#x},+{segs[i][1]:#x})")
print(f"  重叠对数        : {ov}/{max(0,len(segs)-1)}")
cov = sum(s for _, s in segs)
print(f"  size 总和        : {cov} B = 0x{cov:X}")
lo = min(a for a, _ in segs); hi = max(a + s for a, s in segs)
print(f"  覆盖区间         : [0x{lo:X}, 0x{hi:X})  跨度={hi-lo} B")
print(f"  空隙             : {hi - lo - cov} B")
print(f"  文件总长         : {N} B (0x{N:X})")

# ---------- A3. 究竟哪些 offset 上存在"自洽的"12x8 表 ----------
print("\n----- A3. 全文件扫描：所有满足'12项全对齐+零重叠+零空隙'的候选表 -----")
def score_table(buf, off, endian_size, endian_addr, layout):
    """layout: 'tSa' type,size,addr | 't aS'... 返回 (n_valid, n_total, cov, gaps)"""
    items = []
    for i in range(12):
        o = off + i * 8
        if o + 8 > len(buf): return None
        if layout == "tSa":
            t = buf[o]; sz = struct.unpack_from(endian_size + "I", buf, o+1)[0]
            ad = struct.unpack_from(endian_addr + "I", buf, o+5)[0]
        else:
            t = buf[o]; ad = struct.unpack_from(endian_addr + "I", buf, o+1)[0]
            sz = struct.unpack_from(endian_size + "I", buf, o+5)[0]
        items.append((t, sz, ad))
    ok = sum(1 for t, s, a in items if s % 0x1000 == 0 and a % 0x1000 == 0)
    return ok, items

cands = []
for off in range(0, N - 96):
    r = score_table(FW, off, ">", ">", "tSa")
    if r and r[0] == 12:
        cands.append((off, "BE-BE", r[1]))
print(f"  [BE size, BE addr, tSa] 完全对齐的 offset 数 = {len(cands)}")
for off, k, its in cands[:20]:
    cov = sum(s for _, s, _ in its)
    segs = sorted((a, s) for _, s, a in its)
    ov = sum(1 for i in range(1, 12) if segs[i][0] < segs[i-1][0] + segs[i-1][1])
    print(f"    off=0x{off:05X}  cov=0x{cov:X}  ov={ov}")

# ---------- A4. 用 16/32/64 B needle 搜"表只有一份吗" ----------
print("\n----- A4. needle 长度 8/16/32/64 全文件搜索 -----")
for nl in (8, 16, 32, 64, 96):
    pat = FW[T:T+nl]
    hits = []
    start = 0
    while True:
        k = FW.find(pat, start)
        if k < 0: break
        hits.append(k); start = k + 1
    print(f"  needle={nl:>3d}B (取自 0x{T:X})  命中 offset 数={len(hits)}  -> {[hex(h) for h in hits[:12]]}")

# ---------- A5. 用 8B 首项 needle 搜（table 自身的唯一性） ----------
print("\n----- A5. 单条 8B 表项作为 needle -----")
for i in range(12):
    pat = FW[T+i*8: T+i*8+8]
    if pat.count(0) == 8:
        print(f"  [{i:2d}] 全零项，跳过")
        continue
    hits = []
    start = 0
    while True:
        k = FW.find(pat, start)
        if k < 0: break
        hits.append(k); start = k + 1
    print(f"  [{i:2d}] {pat.hex()} 命中={len(hits)} -> {[hex(h) for h in hits[:8]]}")

# ---------- A6. 别的解读方式打分 ----------
print("\n----- A6. 8B 表项的其它解读方式（哪种最自洽？） -----")
variants = [
    ("t:u8 + S:BE32 + A:BE32", "tSa", ">", ">"),
    ("t:u8 + S:LE32 + A:LE32", "tSa", "<", "<"),
    ("t:u8 + A:BE32 + S:BE32", "taS", ">", ">"),
    ("t:u8 + A:LE32 + S:LE32", "taS", "<", "<"),
]
for name, layout, es, ea in variants:
    r = score_table(FW, T, es, ea, layout)
    its = r[1]
    segs = sorted((a, s) for _, s, a in its)
    ov = sum(1 for i in range(1, 12) if segs[i][0] < segs[i-1][0] + segs[i-1][1])
    big = sum(1 for _, s, a in its if s > 0x100000)  # absurd sizes
    print(f"  {name:28s} 对齐={r[0]}/12 重叠={ov} 荒谬size(>1MB)={big}")

print("\nA 部分结束。")
