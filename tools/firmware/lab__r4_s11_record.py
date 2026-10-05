# -*- coding: utf-8 -*-
"""R4-11: 128 字节记录的【字段占用图】—— 逐偏移统计 三份全同 / 机型轴 / 版本轴"""
import numpy as np, collections

S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0), 'capB': ('cap26002816.Cap', 0x4F0)}

def load(p, base):
    d = open(p, 'rb').read(); n = d[base+27]; q = base+32; rows = []
    for _ in range(n):
        rows.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                     ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
    tot = sum(r[1] for r in rows)
    return rows, np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)

R, RAW = {}, {}
for k, (p, b) in S.items():
    R[k], RAW[k] = load(p, b)
ROWS = R['本机']
OFF = np.cumsum([0] + [r[1] for r in ROWS])

print("=" * 100)
print("### 1 记录长度确认：对每个块，扫 L=16/32/64/128/256，看'三份全同'掩模的周期对齐度")
print("=" * 100)
print(f"  {'idx':>3} {'flash':>9} {'size':>6} | " + "  ".join(f"L={L:<3}" for L in (16,32,64,128,256,512)))
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    X = np.stack([RAW[k][o:o+ln] for k in S])
    same = ((X[0] == X[1]) & (X[1] == X[2])).astype(float)
    out = []
    for L in (16, 32, 64, 128, 256, 512):
        n = ln // L
        m = same[:n*L].reshape(n, L)
        out.append(f"{np.abs(m.mean(axis=1)-m.mean()).mean():.3f}")
    print(f"  {i:>3} {ad:#09x} {ln:>6} | " + "  ".join(f"{v:<6}" for v in out))
print("  （数值 = 各行相同率相对总体均值的平均偏差；周期对齐越好该值越大 ⇒ 最大者即真周期）")

print("\n" + "=" * 100)
print("### 2 ★ 128 字节记录的字段占用图（逐偏移，跨所有含周期结构的块平均）")
print("=" * 100)
prof_same = np.zeros(128); prof_mod = np.zeros(128); prof_ver = np.zeros(128); nrec = 0
per_block = {}
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    n = ln // 128
    if n < 8: continue
    X = np.stack([RAW[k][o:o+ln] for k in S])
    same = ((X[0] == X[1]) & (X[1] == X[2])).astype(float)
    modv = (X[0] != X[1]).astype(float)
    ver = (X[1] != X[2]).astype(float)
    ps = same[:n*128].reshape(n, 128).mean(axis=0)
    pm = modv[:n*128].reshape(n, 128).mean(axis=0)
    pv = ver[:n*128].reshape(n, 128).mean(axis=0)
    per_block[i] = (ps, pm, pv)
    prof_same += ps*n; prof_mod += pm*n; prof_ver += pv*n; nrec += n
prof_same /= nrec; prof_mod /= nrec; prof_ver /= nrec
print(f"  （共 {nrec} 条 128B 记录）")
print("  偏移  三份全同%  机型轴差异%  版本轴差异%")
for j in range(128):
    bar = "#" * int(prof_same[j]*40)
    print(f"  {j:>4}   {100*prof_same[j]:>7.1f}  {100*prof_mod[j]:>9.1f}  {100*prof_ver[j]:>9.1f}   {bar}")

print("\n" + "=" * 100)
print("### 3 ★ 分块对比：占用图的周期性/差异（哪些块的记录布局一致）")
print("=" * 100)
ks = sorted(per_block)
print(f"  {'idx':>3} {'flash':>9} | '全同'的 128 偏移里 高同(≥90%) 的个数  | 该块占比")
for i in ks:
    ps, pm, pv = per_block[i]
    hi = int((ps >= 0.9).sum())
    print(f"  {i:>3} {ROWS[i][2]:#09x} | {hi:>30}  | {100*hi/128:5.1f}%")
print("\n  块间占用图相关性（相关系数，只看高结构块）:")
sel = [i for i in ks if (per_block[i][0] >= 0.9).sum() > 8]
for a in range(len(sel)):
    for b in range(a+1, len(sel)):
        ia, ib = sel[a], sel[b]
        c = np.corrcoef(per_block[ia][0], per_block[ib][0])[0, 1]
        print(f"    idx{ia} vs idx{ib}: r = {c:+.3f}")

print("\n" + "=" * 100)
print("### 4 ★ 落到具体字节：以 idx4 为例看 128B 记录内的'恒'区内容（解扰后）")
print("=" * 100)
K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
ph = 572
i = 4; o = OFF[i]; ln = ROWS[i][1]
plain = RAW['本机'][o:o+ln] ^ K[(np.arange(ln)+ph) % 1024]
ps, pm, pv = per_block[4]
print("  记录 0（+0x000-0x07f）解扰后：")
for r in range(0, 128, 16):
    print(f"    +0x{r:03x}  " + " ".join(f"{b:02x}" for b in plain[r:r+16]))
print("  记录 3（+0x180-0x1ff）解扰后：")
for r in range(0x180, 0x200, 16):
    print(f"    +0x{r:03x}  " + " ".join(f"{b:02x}" for b in plain[r:r+16]))
print(": 记录 5（+0x280-0x2ff，处于全零区）")
for r in range(0x280, 0x300, 16):
    print(f"    +0x{r:03x}  " + " ".join(f"{b:02x}" for b in plain[r:r+16]))
