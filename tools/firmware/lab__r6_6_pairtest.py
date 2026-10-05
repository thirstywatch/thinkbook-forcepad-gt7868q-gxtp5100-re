# -*- coding: utf-8 -*-
"""R6-6: (a) 高频字节对 vs 边际乘积（判"真双字节模式"还是"边际效应"）；(b) T3 定位 TF100A 的 I2C1 从机代码"""
import numpy as np, collections

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
PH = 572
d = open('orig_TB14P.bin', 'rb').read(); base = 0x113C
n = d[base + 27]; q = base + 32; ROWS = []
for _ in range(n):
    ROWS.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                 ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
tot = sum(r[1] for r in ROWS)
RAW = np.frombuffer(d[base + 256:base + 256 + tot], dtype=np.uint8)
P = RAW ^ K[(np.arange(len(RAW)) + PH) % 1024]

print("=" * 100)
print("### (a) 相邻字节对：观测频率 vs 「边际乘积」预测 —— 判真模式")
print("=" * 100)
N = len(P)
bj = collections.Counter(((int(P[i]) << 8) | int(P[i + 1])) for i in range(N - 1))
marg = collections.Counter(P.tolist())
print(f"  字节数 {N}；相邻对 {N-1} 个，distinct {len(bj)}")
print(f"  {'字节对':<10} {'观测':>7} {'边际预测':>10} {'观测/预测':>9}")
rows = []
for v, c in bj.most_common(40):
    a, b = v >> 8, v & 0xFF
    exp = (N - 1) * (marg[a] / N) * (marg[b] / N)
    rows.append((c / max(exp, 1e-9), v, c, exp))
rows.sort(reverse=True)
for r, v, c, exp in rows[:20]:
    print(f"  {v:#06x}     {c:>7} {exp:>10.1f} {r:>9.3f}  {'★真双字节模式' if r > 3 else ''}")
print("\n  说明：比值 ≈1 = 纯粹由单字节频率决定（边际效应）；比值 >>3 = 存在真实的双字节搭配。")

print("\n" + "=" * 100)
print("### (a2) 同理检验 4 字节【整词】：观测 vs 边际乘积")
print("=" * 100)
w4 = collections.Counter(bytes(P[i:i+4]) for i in range(0, N - 4, 4))
cnt4 = sum(w4.values())
print(f"  4 字节词（按 4 对齐）{cnt4} 个，distinct {len(w4)}")
print(f"  {'词':<14} {'观测':>6} {'边际预测':>9} {'比值':>8}")
rr = []
for v, c in w4.most_common(30):
    exp = cnt4
    for byt in v:
        exp *= marg[byt] / N
    rr.append((c / max(exp, 1e-9), v, c, exp))
rr.sort(reverse=True)
for r, v, c, exp in rr[:16]:
    print(f"  {v.hex(' '):<14} {c:>6} {exp:>9.2f} {r:>8.1f}  {'★真整词模式' if r > 10 else ''}")

print("\n" + "=" * 100)
print("### (b) T3: TF100A 里的 I2C1 代码区（0x08008940-0x08008B80）")
print("=" * 100)
for i in (1, 2, 3):
    print()
