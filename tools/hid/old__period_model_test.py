"""判定性实验：1 KiB 周期性到底是【明文侧重复的整块】还是【位置型 1024 字节 keystream】？

判据：
  A. 位置型 keystream  C[i] = P[i] ^ K[i % 1024]
       → 密文匹配的【长度谱】是平滑衰减的；不会有"整块 1024 全同"的尖峰
       → 且若 K 非 4 周期，则两份固件在 δ=0xCA4（非 1024 倍数）对齐下不可能有长同段
  B. 内容寻址的整块加密
       → 会出现"整块（乃至多个连续整块）逐字节完全相同"的尖峰
       → 且不依赖对齐偏移

本脚本测长度谱 + 整块全同计数，纯离线。
"""
import os, collections

FW = r"<WORKSPACE>"
data = open(os.path.join(FW, "touchpad_GT7868Q_fw.bin"), "rb").read()

# 用熵剖面确定的加扰区（约 0x1200-0x19800），并对齐到 1024
S, E = 0x1400, 0x19800
seg = data[S:E]
n = len(seg)
L = 1024
nb = n // L
print("加扰区 0x%X-0x%X = %d B = %d 个整块1KiB（尾部余 %d B 丢弃）" % (S, E, n, nb, n % L))
seg = seg[:nb * L]

# ── ① 整块全同计数（stride 1024 与 stride 1024*k）──
print("\n① 相邻整块逐字节全同计数：")
for step in (1, 2, 3, 4, 8):
    cnt = 0
    for b in range(nb - step):
        if seg[b * L:(b + 1) * L] == seg[(b + step) * L:(b + step + 1) * L]:
            cnt += 1
    print("   stride %d KiB : %d 对整块全同（共 %d 对可比）" % (step, cnt, nb - step))

# ── ② 匹配长度谱：stride 1024，长度 ℓ = 1..1024 的匹配率 ──
print("\n② 密文匹配长度谱（stride 1024，匹配率 vs 随机基线）")
base = 1.0 / 256
for l in (1, 2, 4, 8, 16, 32, 48, 64, 128, 256, 384, 512, 768, 1024):
    if l > L:
        break
    tot = 0
    hit = 0
    for i in range(0, n - L - l + 1, 1):
        tot += 1
        if seg[i:i + l] == seg[i + L:i + L + l]:
            hit += 1
    rate = hit / tot
    exp = base ** l if l < 6 else 0.0
    print("   ℓ=%-5d 命中 %-6d / %-6d  匹配率 %.6f   随机期望 %.3g   倍数 %s" % (
        l, hit, tot, rate, exp if l < 6 else 1e-30,
        ("%.0f×" % (rate / exp)) if l < 6 and exp > 0 else "—"))

# ── ③ 反向检验：位置型 keystream 的可否证性 ──
print("\n③ 检验『同一整块的出现次数』分布（内容寻址假说下应有明显重数）")
c = collections.Counter(seg[b * L:(b + 1) * L] for b in range(nb))
mult = collections.Counter(c.values())
print("   不同整块类型数 = %d（总块数 %d）" % (len(c), nb))
for m, k in sorted(mult.items(), reverse=True):
    print("      出现 %2d 次的块：%d 种" % (m, k))
print("   最高频整块出现次数 = %d  => 该块单独贡献的 byte 相等率上限 ≈ %.4f" % (
    max(c.values()), max(c.values()) ** 2 / nb ** 2))
