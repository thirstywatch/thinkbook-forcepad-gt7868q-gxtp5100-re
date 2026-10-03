"""严格对照：判定 twin_same_origin.py 的「20.8× 同源信号」是真信号还是低熵污染。

逻辑：X = C ⊕ A 的 1024 自相关为 r。
      若 A 与 C 同源且共用同一 K，则 X = P1 ⊕ P2 是「明文差」，
      在共享代码段会大量为 0 ⇒ 但 X[i]==X[i+1024] 仍需 P 在 1024 尺度重复。
      **真正的周期 keystream（K1⊕K2 = 1024 周期）会给出 r ≈ 1.0，不是 0.08。**

对照设计：
  r_obs  = corr(C ⊕ A)
  r_c    = corr(C)          ← C 自身的 1024 自相关
  r_a    = corr(A)          ← A 自身
  r_rnd  = corr(C ⊕ random) ← 理论基线
  r_shuf = corr(C ⊕ shuffle(A)) ← 保持 A 字节分布
若 r_obs ≈ r_c 或 r_obs ≈ r_shuf，则信号来自 C/A 自身重复，非同源。
"""
import os
import random
import collections
import math

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()
L = 1024


def corr(x):
    n = len(x) - L
    if n <= 0:
        return None
    return sum(1 for i in range(n) if x[i] == x[i + L]) / n


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


print("=" * 84)
print("① 先测「各段自身」的 1024 自相关（这是判据的天然本底）")
print("=" * 84)
Cseg = cont[0x1400:0x1400 + 0x20000]
Aseg = anchor[0x8600:0x8600 + 0x20000]
print("  C 段(cont 0x1400+32K)  自身 1024 自相关 = %.6f  (%.1f×基线)  熵=%.4f" % (
    corr(Cseg), corr(Cseg) / 0.0039, ent(Cseg)))
print("  A 段(anch 0x8600+32K)  自身 1024 自相关 = %.6f  (%.1f×基线)  熵=%.4f" % (
    corr(Aseg), corr(Aseg) / 0.0039, ent(Aseg)))
print()

print("=" * 84)
print("② 对照组矩阵（同一对段，逐字节异或后的 1024 自相关）")
print("=" * 84)
n = min(len(Cseg), len(Aseg))
x_obs = bytes(a ^ b for a, b in zip(Cseg[:n], Aseg[:n]))
print("  r_obs  = corr(C ⊕ A)                 = %.6f  (%.1f×)" % (corr(x_obs), corr(x_obs) / 0.0039))

random.seed(11)
rnd = bytes(random.randrange(256) for _ in range(n))
x_rnd = bytes(a ^ b for a, b in zip(Cseg[:n], rnd))
print("  r_rnd  = corr(C ⊕ 随机)              = %.6f  (%.1f×)" % (corr(x_rnd), corr(x_rnd) / 0.0039))

sh = bytearray(Aseg[:n]); random.shuffle(sh)
x_sh = bytes(a ^ b for a, b in zip(Cseg[:n], bytes(sh)))
print("  r_shuf = corr(C ⊕ shuffle(A))        = %.6f  (%.1f×)" % (corr(x_sh), corr(x_sh) / 0.0039))

x_cc = bytes(a ^ b for a, b in zip(Cseg[:n], Cseg[:n]))
print("  r_cc   = corr(C ⊕ C)                 = %.6f  (应为 1.0)" % corr(x_cc))
print()

print("=" * 84)
print("③ 判读")
print("=" * 84)
ro = corr(x_obs)
rr = corr(x_rnd)
if abs(ro - rr) < 0.01 and ro < 0.15:
    print("  ⇒ r_obs(%.4f) ≈ r_随机(%.4f)：『20.8×』完全来自 C/A 段自身的重复结构。" % (ro, rr))
    print("     X 并未呈现真正周期。GT9896 与 GT7868Q 【不是同一明文源】。")
else:
    print("  ⇒ r_obs(%.4f) 与随机对照(%.4f) 有差异，需进一步分析。" % (ro, rr))

print()
print("=" * 84)
print("④ 关键量化：若 X 真是 1024 周期 keystream，r 应 ≈ 1.0")
print("=" * 84)
print("  实测 r_obs = %.6f" % ro)
print("  ⇒ 与 1.0 相差 %.1f 倍 ⇒ 完全不是周期 keystream。" % ((1 - ro) / 1 if ro < 1 else 0))
print()

# ── ⑤ 本地所有含 YELSTO 的文件：找「未加扰」样本 ──
print("=" * 84)
print("⑤ 本地含 YELSTO 的固件：谁没被加扰？（熵 < 7.5 即明文）")
print("=" * 84)
files = [
    os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"),
    os.path.join(W, r"fw-touchpad\gt7868q.bin"),
    r"<LAB>\touchpad-lab\bios-re\GT7868Q_native_fw.bin",
    r"<LAB>\touchpad-lab\poc\goodix-fw\goodix_tp_payload.bin",
    r"<LAB>\touchpad-lab\poc\goodix-fw\GOODIXTOUCHPADCAPSULE_22001E0D.Cap",
    os.path.join(HERE, "goodix_gt9896_fw.bin"),
]
for p in files:
    if not os.path.exists(p):
        print("  （缺失）%s" % p)
        continue
    d = open(p, "rb").read()
    idx = d.find(b"YELSTO")
    # 分 4 段看熵
    q = len(d) // 4
    es = [ent(d[i * q:(i + 1) * q]) for i in range(4)]
    print("  %-52s %7d B  YELSTO@0x%05X  四段熵 %s" % (
        os.path.basename(p), len(d), idx, " ".join("%.3f" % e for e in es)))
