"""核查 GT9896 的反常：用它自己「纯区」导出的 K 解它，为何无尖峰？

关键推导复核：
  GT9896 纯区在 0xD900（1024 自相关 = 100%）。若其明文为 0，则 C≡K' 的循环移位。
  Ma = anchor[0xD900 : +1024]
  解码：P[x] = anchor[x] ^ Ma[(x - 0xD900) % 1024]
       ⇒ 相对起点 Sa 的相位 ph 满足 Ma[(0xD900 - Sa + ph) % 1024] == Ma[0]
       ⇒ ph = (Sa - 0xD900) % 1024 = (0x1200 - 0xD900) % 1024 = 256
  所以 ph=256 时，0xD900 那段必须解出全 0。若不成立，说明推导有误。
"""
import os
import collections

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
anc = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()
L = 1024
Ma = anc[0xD900:0xD900 + L]
Sa = 0x1200


def ent(b):
    import math
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


def maxzero(b):
    best = cur = 0
    for x in b:
        cur = cur + 1 if x == 0 else 0
        best = max(best, cur)
    return best


print("=" * 90)
print("① 先确认 GT9896 的「纯区」确实 1024 周期")
print("=" * 90)
seg = anc[0xD900:0xF0FF]
n = len(seg) - L
r = sum(1 for i in range(n) if seg[i] == seg[i + L]) / n
print("  anchor[0xD900:0xF0FF] 长 %d  1024 自相关 = %.6f  (%.1f× 基线)" % (len(seg), r, r / 0.0039))
print()

print("=" * 90)
print("② 用 Ma 解 anchor，逐相位看「0xD900 那段」解出什么")
print("=" * 90)
print("  理论相位应为 ph=256；下面同时列出该相位与最佳相位")
rows = []
for ph in range(L):
    p = bytes(anc[Sa + i] ^ Ma[(i + ph) % L] for i in range(len(anc) - Sa))
    rows.append((p.count(0), maxzero(p), ent(p), ph))
rows.sort(reverse=True)
print("  按「全段 0 计数」排序 Top5：")
for z, mz, e, ph in rows[:5]:
    print("     ph=%4d  0x00=%6d  最长0段=%5d  熵=%.4f" % (ph, z, mz, e))
print()
byph = {ph: (z, mz, e) for z, mz, e, ph in rows}
for ph in (256, 0, 512, 768):
    z, mz, e = byph[ph]
    print("  指定 ph=%4d : 0x00=%6d  最长0段=%5d  熵=%.4f" % (ph, z, mz, e))
print()

print("=" * 90)
print("③ 直接看 ph=256 时 0xD900 段解出的前 64 字节")
print("=" * 90)
ph = 256
base = 0xD900 - Sa
p = bytes(anc[Sa + i] ^ Ma[(i + ph) % L] for i in range(len(anc) - Sa))
seg_dec = p[base:base + 128]
print("  解出:", seg_dec.hex())
print("  全 0 ?", all(x == 0 for x in seg_dec[:64]))
print()

print("=" * 90)
print("④ 反过来：用 Ma 的「循环移位」对齐到文件偏移基准后解码（正规化写法）")
print("=" * 90)
# K'[j] = Ma[(j - 0xD900) % 1024]   —— 与 GT7868Q 的写法完全一致
Kp = bytes(Ma[(j - 0xD900) % L] for j in range(L))
best = []
for s in (0x1000, 0x1200, 0x1400, 0x1900):
    for e in (len(anc),):
        segd = bytes(anc[x] ^ Kp[x % L] for x in range(s, e))
        best.append((segd.count(0), maxzero(segd), ent(segd), s))
for z, mz, e2, s in sorted(best, reverse=True):
    print("  起点 0x%05X : 0x00=%6d  最长0段=%5d  熵=%.4f" % (s, z, mz, e2))
print()
print("  基线：随机 data 的 0x00 期望 = %d（长度 %d / 256）" % (
    (len(anc) - 0x1200) // 256, len(anc) - 0x1200))
print()

print("=" * 90)
print("⑤ 对照：同样写法解 GT7868Q（已知成功）—— 看尖峰该长什么样")
print("=" * 90)
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
raw = open(r"<WORKSPACE>", "rb").read()
K = open(os.path.join(HERE, "GT7868Q_scramble_key.bin"), "rb").read()
segd = bytes(raw[x] ^ K[x % L] for x in range(0x1200, 0x19800))
print("  GT7868Q 主体 0x00=%d  最长0段=%d  熵=%.4f" % (segd.count(0), maxzero(segd), ent(segd)))
