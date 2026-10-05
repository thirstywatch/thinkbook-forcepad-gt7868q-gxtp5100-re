# -*- coding: utf-8 -*-
"""R4-4: 命门测试 —— 上一轮的"解扰"到底是什么变换？掩模从哪来？"""
import numpy as np, collections

O = open('orig_TB14P.bin', 'rb').read()
A = np.frombuffer(open('A_2024.bin','rb').read(), dtype=np.uint8)
K = np.frombuffer(open('K.bin','rb').read(), dtype=np.uint8)
R0, SZ, BASE = 0x113C, 100602, 0x113C+256
RAW = np.frombuffer(O[BASE:BASE+len(A)], dtype=np.uint8)
n = len(A)
print(f"n={n}  BASE=0x{BASE:x}  BASE%1024={BASE%1024}")

d = RAW ^ A

print("\n=== [1] d 真的是 1024 周期吗（正确检验：d[j] == d[j+1024]）===")
eq = (d[:-1024] == d[1024:])
print(f"  d[j]==d[j+1024] 的比例 = {100*eq.mean():.2f}%   （真周期应=100%）")
print(f"  d 的相邻相等率 d[j]==d[j+1] = {100*(d[:-1]==d[1:]).mean():.2f}%")

print("\n=== [2] d[:1024] 是不是 K 的旋转？ ===")
for sh in range(1024):
    if np.array_equal(d[:1024], np.roll(K, -sh)):
        print(f"  ★ d[:1024] == roll(K, {-sh})  ⇒ 相位 = {sh}")
        break
else:
    print("  ✗ d[:1024] 不是 K 的任何旋转")
sh = BASE % 1024
print(f"  与 roll(K, {-sh}) 的逐字节相等率 = {100*(d[:1024]==np.roll(K,-sh)).mean():.2f}%")
print(f"  K 的零值位置={[i for i in range(1024) if K[i]==0]}  (BASE%1024={sh})")

print("\n=== [3] 逐个检验候选变换是否成立（全 100352 字节）===")
Ks = np.roll(K, -sh)                      # 1024 B 掩模
Ksf = np.tile(Ks, n // 1024 + 1)[:n]      # 铺满全长的掩模
cands = {
  "A == RAW ^ K_shift           ": A == (RAW ^ Ksf),
  "A == (RAW - K_shift) mod 256 ": A == ((RAW.astype(int) - Ksf) % 256),
  "A == (RAW + K_shift) mod 256 ": A == ((RAW.astype(int) + Ksf) % 256),
  "A == RAW                     ": A == RAW,
}
for k, v in cands.items():
    print(f"  {k}: {100*v.mean():.2f}%")

print("\n=== [4] ★ RAW 自身有没有 1024 周期结构？ ===")
for lag in (256, 512, 1024, 2048, 4096, 8192):
    m = (RAW[:-lag] == RAW[lag:]).mean()
    print(f"  P(RAW[j]==RAW[j+{lag}]) = {100*m:.3f}%   (均匀基线 0.3906%)")

print("\n=== [5] A（上一轮解扰产物）自身有没有 1024 周期结构？ ===")
for lag in (256, 512, 1024, 2048, 4096, 8192):
    m = (A[:-lag] == A[lag:]).mean()
    print(f"  P(A[j]==A[j+{lag}]) = {100*m:.3f}%")

print("\n=== [6] 关键：A 的零 与 RAW的什么条件等价？ ===")
z = (A == 0)
print(f"  A 的零% = {100*z.mean():.2f}%   共 {int(z.sum())}")
print(f"  在 A==0 处，RAW==K_shift 的比例 = {100*(RAW[z]==Ks[z]).mean():.2f}%")
print(f"  在 A==0 处，RAW 的取值 top5 = {collections.Counter(RAW[z].tolist()).most_common(5)}")
print(f"  在 A!=0 处，RAW 的方差 = {RAW[~z].astype(int).var():.0f} (均匀应≈5461)")
print(f"  RAW 整体方差 = {RAW.astype(int).var():.0f}")

print("\n=== [7] 掩模 d 在“A 非零处”的分布 ===")
dnz = d[~z]
print(f"  非零处 d 的取值数 = {len(set(dnz.tolist()))}  方差 = {dnz.astype(int).var():.0f}")
print(f"  非零处 d 的 top5 = {collections.Counter(dnz.tolist()).most_common(5)}")
print(f"  ⇒ 若 d 是固定掩模，非零处 d 应只有 256 种取值且分布集中/或均匀")

print("\n=== [8] K 与 RAW 某窗口的关系 ===")
for x in (0, 0x1000, 0x10000, 0x18000):
    if x+1024 <= len(RAW):
        print(f"  K vs RAW[{x:#x}:{x+1024:#x}] 相等率 = {100*(K==RAW[x:x+1024]).mean():.2f}%")
# K 是否是某个 1024 窗口的旋转
for x in range(0, min(len(RAW)-1024, 40000), 1024):
    w = RAW[x:x+1024]
    for sh2 in range(0, 1024, 4):
        if np.array_equal(K, np.roll(w, -sh2)):
            print(f"  ★ K == roll(RAW[{x:#x}:{x+1024:#x}], {-sh2})")
print("  (窗口扫描结束)")
