"""最直接的判据：按位置 mod L 分组后，各类字节直方图的"众数占比"。
  · 强密码（无重复密钥流）=> 类内分布被"很多个不同平移"混合 => 众数占比 ≈ 均匀值
  · 周期加扰 / 未加扰的明文 => 类内分布保持不均匀 => 众数占比明显高于均匀值
"""
import os, collections, random, hashlib

BIN = r"<WORKSPACE>"
d = open(BIN, "rb").read()
seg = d[0x1400:0x19A00]
n = len(seg)

def mode_share(data, L):
    ms = []
    for j in range(L):
        cls = data[j::L]
        if len(cls) < 200:
            continue
        c = collections.Counter(cls)
        ms.append(c.most_common(1)[0][1] / len(cls))
    return sum(ms) / len(ms), min(ms), max(ms)

def strong_stream(data, seed):
    out = bytearray(len(data))
    for off in range(0, len(data), 32):
        ks = hashlib.sha256(seed + off.to_bytes(4, "little")).digest()
        for i, b in enumerate(data[off:off + 32]):
            out[off + i] = b ^ ks[i]
    return bytes(out)

random.seed(99)
rand = bytes(random.getrandbits(8) for _ in range(n))

# 纯均匀随机的理论基线（含有限样本偏差）
print("均匀随机基线：众数占比 ≈ 1/256 + 有限样本上偏")
for L in (8, 16, 32, 64):
    m, lo, hi = mode_share(rand, L)
    print("   L=%-4d  纯随机  mean=%.5f" % (L, m))

print()
models = [("真数据", seg), ("强流密码代理", strong_stream(seg, b"s")), ("纯随机", rand)]
print("%-14s %-8s %-10s %-10s %-10s" % ("样本", "L", "mean", "min", "max"))
for nm, data in models:
    for L in (16, 32, 64):
        m, lo, hi = mode_share(data, L)
        print("%-14s %-8d %-10.5f %-10.5f %-10.5f" % (nm, L, m, lo, hi))
    print()
