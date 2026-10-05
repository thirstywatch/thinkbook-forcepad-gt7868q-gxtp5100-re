# -*- coding: utf-8 -*-
"""R4-8: 13 块细粒度解析 —— 用"版本轴"（capA→capB 仅版本变）定位字段边界"""
import numpy as np, collections

K = np.frombuffer(open('K.bin','rb').read(), dtype=np.uint8)
S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0), 'capB': ('cap26002816.Cap', 0x4F0)}
META = {'本机': 'CID=1C VID=2.3.5', 'capA': 'CID=0C VID=2.0.30', 'capB': 'CID=0C VID=2.0.40'}

def load(p, base):
    d = open(p, 'rb').read(); n = d[base+27]; q = base+32; rows = []
    for _ in range(n):
        t = d[q]; ln = (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4]
        ad = ((d[q+5] << 8) | d[q+6]) << 8
        rows.append((t, ln, ad)); q += 8
    tot = sum(r[1] for r in rows)
    raw = np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)
    ph = 572
    plain = raw ^ K[(np.arange(len(raw)) + ph) % 1024]
    return rows, raw, plain

D = {}
for k, (p, b) in S.items():
    rows, raw, plain = load(p, b)
    D[k] = dict(rows=rows, raw=raw, plain=plain)
ROWS = D['本机']['rows']

def runs(idx, maxgap=1):
    """把偏移集合压成连续段"""
    if len(idx) == 0: return []
    idx = np.sort(idx); out = []; s = idx[0]; p = idx[0]
    for v in idx[1:]:
        if v <= p + maxgap: p = v
        else: out.append((s, p)); s = v; p = v
    out.append((s, p)); return out

print("=" * 100)
print("### 1. 版本轴（capA 2.0.30 → capB 2.0.40，同 CID）：差异落在哪里？")
print("=" * 100)
print(f"  {'idx':>3} {'flash':>9} {'size':>6} {'差异字节':>8} {'差异段数':>8}  最长差异段 / 段长分布")
for i, (t, ln, ad) in enumerate(ROWS):
    o = sum(r[1] for r in ROWS[:i])
    a = D['capA']['raw'][o:o+ln]; b = D['capB']['raw'][o:o+ln]
    dif = np.nonzero(a != b)[0]
    rs = runs(dif)
    lens = sorted((e-s+1 for s, e in rs), reverse=True)
    print(f"  {i:>3} {ad:#09x} {ln:>6} {len(dif):>8} {len(rs):>8}  最长={lens[0] if lens else 0}"
          f"  前8段长={lens[:8]}")

print("\n" + "=" * 100)
print("### 2. 机型轴（本机 CID=1C  vs  capA CID=0C）：差异是否均匀？")
print("=" * 100)
print(f"  {'idx':>3} {'flash':>9} {'size':>6} {'差异字节':>8} {'差异段数':>8} {'最长段':>7}  前6段长")
for i, (t, ln, ad) in enumerate(ROWS):
    o = sum(r[1] for r in ROWS[:i])
    a = D['本机']['raw'][o:o+ln]; b = D['capA']['raw'][o:o+ln]
    dif = np.nonzero(a != b)[0]; rs = runs(dif)
    lens = sorted((e-s+1 for s, e in rs), reverse=True)
    print(f"  {i:>3} {ad:#09x} {ln:>6} {len(dif):>8} {len(rs):>8} {lens[0] if lens else 0:>7}  {lens[:6]}")

print("\n" + "=" * 100)
print("### 3. ★ idx6 (flash 0x1E000, 芯片级常量): 与 capA 不同的那 45 字节在哪？")
print("=" * 100)
i = 6; o = sum(r[1] for r in ROWS[:i]); ln = ROWS[i][1]
a = D['本机']['raw'][o:o+ln]; b = D['capA']['raw'][o:o+ln]
dif = np.nonzero(a != b)[0]
print(f"  差异 {len(dif)} 字节，段: {runs(dif, maxgap=0)[:20]}")
print("  逐字节 (偏移: 本机 vs capA)：")
for v in dif[:60]:
    print(f"    +0x{v:04x}  本机 {a[v]:02x}  capA {b[v]:02x}   (mod8={v%8} mod4={v%4})")
print("  差异偏移 mod 4 分布:", collections.Counter((dif % 4).tolist()))
print("  差异偏移 mod 8 分布:", collections.Counter((dif % 8).tolist()))

print("\n" + "=" * 100)
print("### 4. ★ idx0 (flash 0x0FF00, ISP 2KB)：变动的 256 B 尾部长什么样")
print("=" * 100)
i = 0; o = 0; ln = ROWS[0][1]
for nm in ('capA', 'capB'):
    a = D['本机']['raw'][o:o+ln]; b = D[nm]['raw'][o:o+ln]
    dif = np.nonzero(a != b)[0]
    print(f"  本机 vs {nm}: 差异 {len(dif)} 字节，最早=+0x{dif.min():x} 最晚=+0x{dif.max():x} "
          f"-> 前 {dif.min()} B 相同")
print("  尾部 256 B (本机 / capA) 前 64 字节对比:")
print("   本机 ", " ".join(f"{x:02x}" for x in D['本机']['raw'][ln-256:ln-192]))
print("   capA ", " ".join(f"{x:02x}" for x in D['capA']['raw'][ln-256:ln-192]))
print("  ⇒ 用 6 次幂等检验：尾部是否每样本不同 vs 前 1792 B 三份全同")
A3 = np.stack([D[k]['raw'][o:o+ln] for k in ('本机', 'capA', 'capB')])
same3 = (A3[0] == A3[1]) & (A3[1] == A3[2])
print(f"     三份全同的字节数 = {int(same3.sum())}/{ln}；第一批不同出现在 +0x{np.nonzero(~same3)[0].min():x}")

print("\n" + "=" * 100)
print("### 5. 每块'骨架比例'（三份全同 / 全不同）与'版本敏感'比例")
print("=" * 100)
print(f"  {'idx':>3} {'type':>5} {'flash':>9} {'size':>6} {'三份全同':>9} {'同版本异':>9} {'三份全异':>9} 判读")
for i, (t, ln, ad) in enumerate(ROWS):
    o = sum(r[1] for r in ROWS[:i])
    A3 = np.stack([D[k]['raw'][o:o+ln] for k in ('本机', 'capA', 'capB')])
    s3 = int(((A3[0] == A3[1]) & (A3[1] == A3[2])).sum())
    d3 = int(((A3[0] != A3[1]) & (A3[1] != A3[2])).sum())
    vonly = ln - s3 - d3
    kind = ("芯片/版本级常量" if s3 > 0.9*ln else
            ("骨架+参数" if s3 > 0.4*ln else
             ("全量生成" if d3 > 0.6*ln else "混合")))
    print(f"  {i:>3} {t:#05x} {ad:#09x} {ln:>6} {s3:>9} {vonly:>9} {d3:>9} {kind}")
