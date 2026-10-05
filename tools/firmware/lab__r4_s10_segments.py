# -*- coding: utf-8 -*-
"""R4-10: 13 块精确分段 —— 硬骨架 / 机型区 / 版本区 的边界表"""
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

print("=" * 104)
print("### 1 ★ 每块的【硬骨架】区间：三份逐字节全同的最长连续段")
print("=" * 104)
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    X = np.stack([RAW[k][o:o+ln] for k in S])
    same = (X[0] == X[1]) & (X[1] == X[2])
    # 连续段
    segs = []; s = None
    for j in range(ln):
        if same[j] and s is None: s = j
        elif not same[j] and s is not None: segs.append((s, j-1)); s = None
    if s is not None: segs.append((s, ln-1))
    big = [x for x in segs if x[1]-x[0]+1 >= 32]
    tot = int(same.sum())
    print(f"\n  idx{i:>2} {ad:#07x} type{t:#04x} size {ln}  全同 {tot} ({100*tot/ln:.1f}%)  "
          f"≥32B 的恒定段 {len(big)} 个：")
    for a, b in big[:12]:
        # 恒定段内容是否全零
        allzero = bool((RAW['本机'][o+a:o+b+1] == 0).all())
        print(f"      +0x{a:04x}..+0x{b:04x}  ({b-a+1:>5} B)  {'【全零填充】' if allzero else '【非零常量】'}")

print("\n" + "=" * 104)
print("### 2 ★ 分段表：把每块切成'变率相同'的区段（机型轴）")
print("=" * 104)
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    dm = (RAW['本机'][o:o+ln] != RAW['capA'][o:o+ln]).astype(int)
    W = max(64, ln // 64)
    prof = dm[:ln//W*W].reshape(-1, W).mean(axis=1)
    # 二值化
    b = (prof > 0.10).astype(int)
    # 合并连续相同
    segs = []; s = 0
    for j in range(1, len(b)):
        if b[j] != b[j-1]: segs.append((s*W, j*W-1, b[j-1])); s = j
    segs.append((s*W, len(b)*W-1, b[-1]))
    txt = " ".join(f"{'变' if v else '恒'}{a:#x}-{c:#x}" for a, c, v in segs if c-a >= W-1)
    print(f"  idx{i:>2} {ad:#07x} ({ln}B, 窗口 {W}B): {txt}")

print("\n" + "=" * 104)
print("### 3 ★ 版本轴差异：位置是否成片？（版本轴 16 等分密度）")
print("=" * 104)
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    dv = (RAW['capA'][o:o+ln] != RAW['capB'][o:o+ln]).astype(int)
    prof = dv.reshape(16, -1).mean(axis=1)
    print(f"  idx{i:>2} {ad:#07x} 版本轴差异密度: " + " ".join(f"{100*v:3.0f}" for v in prof) + "%")

print("\n" + "=" * 104)
print("### 4 ★ 边界对齐性：所有'变率骤变点'的绝对偏移是否都是 2 的幂/整千？")
print("=" * 104)
allb = collections.Counter()
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    dm = (RAW['本机'][o:o+ln] != RAW['capA'][o:o+ln]).astype(int)
    W = 64
    prof = dm[:ln//W*W].reshape(-1, W).mean(axis=1)
    b = (prof > 0.10).astype(int)
    for j in range(1, len(b)):
        if b[j] != b[j-1]:
            allb[j*W] += 1
print("  变率骤变点（块内偏移，出现次数≥2）：")
for k, v in sorted(allb.items()):
    if v >= 2:
        print(f"    +0x{k:04x} ({k})  ×{v}" + ("   ★2 的幂" if k & (k-1) == 0 else ""))

print("\n" + "=" * 104)
print("### 5 ★ idx9 (flash 0x00000) 四段结构细看（机型轴密度最大的是哪段）")
print("=" * 104)
i = 9; o = OFF[i]; ln = ROWS[i][1]
dm = (RAW['本机'][o:o+ln] != RAW['capA'][o:o+ln]).astype(int)
dv = (RAW['capA'][o:o+ln] != RAW['capB'][o:o+ln]).astype(int)
for a in range(0, ln, 256):
    print(f"    +0x{a:04x}..+0x{a+255:04x}  机型轴差异 {100*dm[a:a+256].mean():5.1f}%   "
          f"版本轴 {100*dv[a:a+256].mean():5.1f}%   本机零率 {100*(RAW['本机'][o+a:o+a+256]==0).mean():5.1f}%")
