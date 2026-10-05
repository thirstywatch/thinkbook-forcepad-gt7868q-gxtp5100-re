# -*- coding: utf-8 -*-
"""R4-12: 用解扰后的【非零掩模自相关】找每个块的记录步长；并给每块的区段解剖"""
import numpy as np, collections

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
PH = 572
S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0), 'capB': ('cap26002816.Cap', 0x4F0)}

def load(p, base):
    d = open(p, 'rb').read(); n = d[base+27]; q = base+32; rows = []
    for _ in range(n):
        rows.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                     ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
    tot = sum(r[1] for r in rows)
    raw = np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)
    return rows, raw, raw ^ K[(np.arange(len(raw)) + PH) % 1024]

R, RAW, PLAIN = {}, {}, {}
for k, (p, b) in S.items():
    R[k], RAW[k], PLAIN[k] = load(p, b)
ROWS = R['本机']; OFF = np.cumsum([0] + [r[1] for r in ROWS])

print("=" * 100)
print("### 1 ★ 非零掩模自相关 → 记录步长（正对照：打乱后应无峰）")
print("=" * 100)
def best_lags(mask, maxlag=512, top=4):
    m = mask.astype(float); m = m - m.mean()
    ac = np.correlate(m, m, 'full')[len(m)-1:]
    ac /= ac[0]
    idx = np.argsort(ac[2:maxlag])[::-1] + 2
    return [(int(i), float(ac[i])) for i in idx[:top]], ac[2:maxlag].max()
print(f"  {'idx':>3} {'flash':>9} {'size':>6} {'零%':>6} | 最强 lag(top4)  | 打乱对照最强")
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    p = PLAIN['本机'][o:o+ln]
    mask = (p != 0)
    top, mx = best_lags(mask, min(512, ln//2))
    rng = np.random.default_rng(3)
    sh = rng.permutation(mask)
    _, smx = best_lags(sh, min(512, ln//2))
    print(f"  {i:>3} {ad:#09x} {ln:>6} {100*(~mask).mean():>6.1f} | " +
          " ".join(f"lag{l}({v:+.3f})" for l, v in top) + f" | {smx:+.3f}")

print("\n" + "=" * 100)
print("### 2 ★ 每块区段解剖（解扰后，本机）：零区 / 恒定区 / 可变区")
print("=" * 100)
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    p = PLAIN['本机'][o:o+ln]
    X = np.stack([RAW[k][o:o+ln] for k in S])
    same = (X[0] == X[1]) & (X[1] == X[2])
    zero = (p == 0)
    modv = (X[0] != X[1])
    ver = (X[1] != X[2])
    # 以 256B 为窗输出特征
    print(f"\n  --- idx{i} flash {ad:#07x} type{t:#04x} size {ln} ---")
    print("      +偏移    零%    三份全同%  机型变%  版本变%")
    for a in range(0, ln, 256):
        s = slice(a, a+256)
        print(f"     +0x{a:04x}  {100*zero[s].mean():5.1f}   {100*same[s].mean():8.1f}  "
              f"{100*modv[s].mean():7.1f}  {100*ver[s].mean():7.1f}")

print("\n" + "=" * 100)
print("### 3 ★ idx4（flash 0x0A000）解扰后逐 16 字节（看记录形态）")
print("=" * 100)
o = OFF[4]; ln = ROWS[4][1]; p = PLAIN['本机'][o:o+ln]
for a in range(0, 1024, 16):
    print(f"    +0x{a:04x}  " + " ".join(f"{b:02x}" for b in p[a:a+16]))
print("    ...（+0x0ab4 起）")
for a in range(0x0ab4, 0x0ab4+64, 16):
    print(f"    +0x{a:04x}  " + " ".join(f"{b:02x}" for b in p[a:a+16]))
