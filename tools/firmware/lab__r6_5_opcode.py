# -*- coding: utf-8 -*-
"""R6-5: 定长指令假说检验 —— 4 字节词内部各字节位置的熵"""
import numpy as np, collections, math

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
PH = 572
d = open('orig_TB14P.bin', 'rb').read()
base = 0x113C
n = d[base + 27]; q = base + 32; ROWS = []
for _ in range(n):
    ROWS.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                 ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
tot = sum(r[1] for r in ROWS)
RAW = np.frombuffer(d[base + 256:base + 256 + tot], dtype=np.uint8)
OFF = np.cumsum([0] + [r[1] for r in ROWS])
P = RAW ^ K[(np.arange(len(RAW)) + PH) % 1024]


def ent(c, n):
    return -sum((v / n) * math.log2(v / n) for v in c.values())


print("=" * 104)
print("### 1 定长指令假说：4 字节词内部各位置熵（前 2 字节若集中 = 操作码，后 2 字节高熵 = 操作数）")
print("=" * 104)
print(f"  {'idx':>3} {'type':>5} {'flash':>9} | {'b0熵':>7} {'b1熵':>7} {'b2熵':>7} {'b3熵':>7} | "
      f"{'前缀数':>7} {'top1':>7} 判读")
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]; w = P[o:o + ln - ln % 4].reshape(-1, 4); m = len(w)
    es = [ent(collections.Counter(w[:, c].tolist()), m) for c in range(4)]
    pre = collections.Counter((int(a) << 8) | int(b) for a, b in zip(w[:, 0], w[:, 1]))
    top = pre.most_common(1)[0]
    tag = "★操作码+操作数" if (es[0] < 6.5 or es[1] < 6.5) and max(es[2], es[3]) > 7.0 else ""
    print(f"  {i:>3} {t:#05x} {ad:#09x} | {es[0]:7.3f} {es[1]:7.3f} {es[2]:7.3f} {es[3]:7.3f} | "
          f"{len(pre):>7} {100 * top[1] / m:6.2f}% {top[0]:#06x} {tag}")

print("\n" + "=" * 104)
print("### 2 全载荷 A 合并：2 字节前缀（操作码候选）的高频值")
print("=" * 104)
allw = []; o = 0
for i, (t, ln, ad) in enumerate(ROWS):
    allw.append(P[o:o + ln - ln % 4].reshape(-1, 4)); o += ln
W = np.vstack(allw); m = len(W)
pre = collections.Counter((int(a) << 8) | int(b) for a, b in zip(W[:, 0], W[:, 1]))
print(f"  共 {m} 个词, distinct 前缀 {len(pre)}")
print(f"  前 24 高频前缀（合计占 {100 * sum(c for _, c in pre.most_common(24)) / m:.1f}%）：")
for v, c in pre.most_common(24):
    print(f"    {v:#06x}  (字节 {v >> 8:02x} {v & 0xff:02x})  x{c:<5} {100 * c / m:5.2f}%")
print(f"  对照：均匀时单个前缀占 {100 / 65536:.5f}%")
es = [ent(collections.Counter(W[:, c].tolist()), m) for c in range(4)]
print(f"  全体字节熵 = {[round(x, 3) for x in es]}   (上限 8.0)")

print("\n" + "=" * 104)
print("### 3 各字节位置各自的集中度")
print("=" * 104)
for c, nm in ((0, '字节0 首'), (1, '字节1'), (2, '字节2'), (3, '字节3 末')):
    cc = collections.Counter(W[:, c].tolist())
    t0 = cc.most_common(1)[0]
    print(f"  {nm:<12} distinct {len(cc):>3}/256  top1 {t0[0]:#04x} x{t0[1]:<5} "
          f"({100 * t0[1] / m:5.2f}%)  熵 {ent(cc, m):.3f}")
