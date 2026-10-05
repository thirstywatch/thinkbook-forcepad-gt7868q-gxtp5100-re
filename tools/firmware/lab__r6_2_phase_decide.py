# -*- coding: utf-8 -*-
"""R6-2: 决定性检验 —— 逐块比较 RAW 与"解扰后"的结构，看 K 是否真的对全部 13 块都成立"""
import numpy as np, collections, math

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
PH = 572
S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0), 'capB': ('cap26002816.Cap', 0x4F0)}

def load(p, base):
    d = open(p, 'rb').read(); n = d[base+27]; q = base+32; rows = []
    for _ in range(n):
        rows.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                     ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
    tot = sum(r[1] for r in rows)
    return rows, np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)

ROWS, RAW = load(*S['本机'])
OFF = np.cumsum([0] + [r[1] for r in ROWS])

def stats(x):
    n = len(x); c = collections.Counter(x.tolist())
    H = -sum((v/n)*math.log2(v/n) for v in c.values())
    z = int((x == 0).sum())
    best = cur = 0
    for v in x:
        cur = cur + 1 if v == 0 else 0
        best = max(best, cur)
    top = c.most_common(1)[0]
    return H, 100*z/n, best, len(c), top[0], 100*top[1]/n

NMAX = np.arange(len(RAW)) % 1024
PLAIN = RAW ^ K[(NMAX + PH) % 1024]

print("=" * 108)
print("### ★★★ 逐块：RAW（存储态） vs PLAIN（K 解扰后）—— K 对哪几块有效？")
print("=" * 108)
print(f"  {'idx':>3} {'type':>5} {'flash':>9} {'size':>6} | {'RAW 熵':>7} {'RAW 零%':>7} {'RAW 最长零段':>10} "
      f"{'RAW 值数':>8} | {'PLAIN 熵':>8} {'PLAIN 零%':>8} {'PLAIN 最长零段':>12} {'PLAIN 值数':>9}")
res = []
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    r = RAW[o:o+ln]; p = PLAIN[o:o+ln]
    hr, zr, br, cr, tr, pr = stats(r)
    hp, zp, bp, cp, tp, pp = stats(p)
    res.append((i, t, ad, ln, hr, zr, br, cr, hp, zp, bp, cp))
    print(f"  {i:>3} {t:#05x} {ad:#09x} {ln:>6} | {hr:>7.3f} {zr:>7.2f} {br:>10} {cr:>8} | "
          f"{hp:>8.3f} {zp:>8.2f} {bp:>12} {cp:>9}")

print("\n" + "=" * 108)
print("### ★★★ 每块【独立】扫全部 1024 个相位：用三个判据各自找最优")
print("=" * 108)
print(f"  {'idx':>3} {'type':>5} | 最优相位(零最多) | 次优  | 倍率 | 最优相位(最长零段最大) | RAW 原始(=相位0相对) | 全局相位572结果")
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]; r = RAW[o:o+ln]
    n = len(r); base = np.arange(n)
    zs = np.empty(1024, dtype=int); ls = np.empty(1024, dtype=int)
    for ph in range(1024):
        d = r ^ K[(base + ph) % 1024]
        zs[ph] = int((d == 0).sum())
        best = cur = 0
        for v in d:
            cur = cur + 1 if v == 0 else 0
            best = max(best, cur)
        ls[ph] = best
    order = np.argsort(zs)[::-1]
    order2 = np.argsort(ls)[::-1]
    ratio = zs[order[0]] / max(1, zs[order[1]])
    print(f"  {i:>3} {t:#05x} | ph={order[0]:<14} {zs[order[0]]:>5}/{zs[order[1]]:<5} {ratio:>5.2f}× "
          f"| ph={order2[0]:<21} | ph0: 零{zs[0]:>5} 最长零段{ls[0]:>4} | 572: 零{zs[PH]:>5} 最长零段{ls[PH]:>4}")

print("\n" + "=" * 108)
print("### ★★ 判据校准：真代码 / 明文数据 / 随机 的 (熵, 零%, 最长零段)")
print("=" * 108)
O = open('orig_TB14P.bin', 'rb').read()
TF = np.frombuffer(O[0x19ABC:0x2775C], dtype=np.uint8)
rng = np.random.default_rng(5)
for nm, x in (("TF100A 真 Cortex-M 代码", TF),
              ("纯随机", rng.integers(0, 256, 12288).astype(np.uint8)),
              ("载荷A type0x03 idx6(常量表)", PLAIN[OFF[6]:OFF[6]+ROWS[6][1]]),
              ("载荷A type0x03 idx4(74%零)", PLAIN[OFF[4]:OFF[4]+ROWS[4][1]]),
              ("载荷A type0x02 idx11 RAW", RAW[OFF[11]:OFF[11]+ROWS[11][1]]),
              ("载荷A type0x02 idx11 PLAIN", PLAIN[OFF[11]:OFF[11]+ROWS[11][1]])):
    H, z, b, c, t0, p1 = stats(x)
    print(f"  {nm:<28} 熵 {H:6.3f}  零% {z:6.2f}  最长零段 {b:>4}  值数 {c:>3}  top1 {t0:#04x}×{p1:.2f}%")
