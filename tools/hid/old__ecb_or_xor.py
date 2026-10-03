"""定性检验：GT7868Q 那 100KB 是【AES-ECB 之类的强分组密码】还是【周期性加扰(重复密钥 XOR/置换)】？

判据：
  · AES-ECB 输出每个字节位置 mod L 都是均匀分布 => 类内熵 ≈ 8.0（与随机对照相同）
  · 重复密钥 XOR(C[i]=P[i]^K[i mod L]) 时，类内分布 = 明文分布平移
      => 明文分布不均匀（代码/数据必然不均匀）则【类内熵显著低于随机对照】
      => 这是"每字节独立、周期 L"的铁证，且密钥可被恢复
"""
import os, collections, math, random, struct

BIN = r"<WORKSPACE>"
d = open(BIN, "rb").read()
lo, hi = 0x1400, 0x19A00
seg = d[lo:hi]
n = len(seg)
print("区间 0x%X..0x%X  长度 %d" % (lo, hi, n))

def entropy(vals):
    c = collections.Counter(vals)
    t = len(vals)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

print("\n全区间字节熵 = %.4f" % entropy(seg))

# 对照：把同样的字节随机打乱（分布完全相同，只是顺序被打乱）
rnd = bytearray(seg)
random.seed(1234)
random.shuffle(rnd)
rnd = bytes(rnd)

print("\n%-6s %-12s %-14s %-14s %s" % ("L", "类内熵(真)", "类内熵(打乱对照)", "差值", "判定"))
for L in (2, 4, 8, 16, 32, 64, 128, 256, 512):
    Hs = []
    Hc = []
    for j in range(L):
        cls = seg[j::L]
        ctr = rnd[j::L]
        if len(cls) < 40:
            continue
        Hs.append(entropy(cls))
        Hc.append(entropy(ctr))
    hs = sum(Hs) / len(Hs)
    hc = sum(Hc) / len(Hc)
    diff = hs - hc
    verdict = "★ 有周期性（类内熵明显偏低）" if diff < -0.02 else ("—  无周期性" if diff > -0.005 else "? 边缘")
    print("%-6d %-14.4f %-16.4f %+-14.4f %s" % (L, hs, hc, diff, verdict))

# 另一条独立判据：按 L 分组后，各类的"字节直方图"是否互为平移（XOR 特征）
print("\n=== 类内分布形状：各类的众数占比（XOR 加扰下应普遍偏高）===")
for L in (16, 32):
    modes = []
    for j in range(L):
        cls = seg[j::L]
        if len(cls) < 40:
            continue
        c = collections.Counter(cls)
        modes.append(c.most_common(1)[0][1] / len(cls))
    print("  L=%-4d 各种众数占比：min=%.4f  mean=%.4f  max=%.4f  (均匀随机应≈%.4f)"
          % (L, min(modes), sum(modes) / len(modes), max(modes), 1 / 256))

# 第三条：整体"字节取值集中度"——强分组密码应接近均匀
print("\n=== 整体字节直方图（前 12 个最常见值）===")
c = collections.Counter(seg)
for v, k in c.most_common(12):
    print("   0x%02X : %6d  (%.4f%%, 均匀应 %.4f%%)" % (v, k, 100 * k / n, 100 / 256))
