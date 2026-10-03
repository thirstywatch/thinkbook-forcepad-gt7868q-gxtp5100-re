"""真相核查：kextract.py 的「K 候选 100% 相同」结论是否成立？

疑点：
  cont   纯区起点 0x084F0  前 96B = ab1f9dab3b3bcdcb...  （高熵乱码）
  anchor 纯区起点 0x0D900  前 96B = 0000000080041020...  （低熵结构化）
  两者若互为循环移位，熵应相同 ⇒ 内部矛盾。必须逐项验证。
"""
import os
import collections
import math

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()
L = 1024


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


Mc = cont[0x084F0:0x084F0 + L]
Ma = anchor[0x0D900:0x0D900 + L]
kc = cont[0x08CF0:0x08CF0 + L]
ka = anchor[0x0E100:0x0E100 + L]

print("=" * 88)
print("① 四个 1024 B 块的基本属性")
print("=" * 88)
for name, b in (("Mc(cont 0x084F0)", Mc), ("Ma(anch 0x0D900)", Ma),
                ("kc(cont 0x08CF0)", kc), ("ka(anch 0x0E100)", ka)):
    c = collections.Counter(b)
    top = c.most_common(3)
    print("  %-20s 熵=%.4f  唯一字节=%d  最高频=%s" % (name, ent(b), len(c), top))
print()
print("  Mc == kc ? %s" % (Mc == kc))
print("  Ma == ka ? %s" % (Ma == ka))
print()

print("=" * 88)
print("② Mc 与 Ma 的全部相位匹配率（找峰值）")
print("=" * 88)
rates = []
for rot in range(L):
    rot_ma = Ma[rot:] + Ma[:rot]
    eq = sum(1 for x, y in zip(Mc, rot_ma) if x == y) / L
    rates.append((eq, rot))
rates.sort(reverse=True)
print("  前 6 名：")
for eq, rot in rates[:6]:
    print("     rot=%4d  相同率=%.4f" % (rot, eq))
print("  （随机基线 = 1/256 = 0.0039）")
print()
print("  kc 与 ka 同样测：")
rates2 = []
for rot in range(L):
    rot_ka = ka[rot:] + ka[:rot]
    eq = sum(1 for x, y in zip(kc, rot_ka) if x == y) / L
    rates2.append((eq, rot))
rates2.sort(reverse=True)
for eq, rot in rates2[:6]:
    print("     rot=%4d  相同率=%.4f" % (rot, eq))
print()

print("=" * 88)
print("③ 关键：Mc 是否「常量」或「低熵周期」？（决定它能不能当 K）")
print("=" * 88)
print("  Mc 前 64B:", Mc[:64].hex())
print("  Mc 中段64B:", Mc[480:544].hex())
print("  Mc 后 64B:", Mc[-64:].hex())
print()
print("  Ma 前 64B:", Ma[:64].hex())
print("  Ma 中段64B:", Ma[480:544].hex())
print("  Ma 后 64B:", Ma[-64:].hex())
print()

print("=" * 88)
print("④ Mc 内部的字节分布（若为 1024 周期 keystream，应接近均匀）")
print("=" * 88)
c = collections.Counter(Mc)
print("  唯一字节数 = %d / 256" % len(c))
vals = sorted(c.values())
print("  出现次数 min=%d  max=%d  均值=%.2f" % (min(vals), max(vals), sum(vals) / len(vals)))
print()

print("=" * 88)
print("⑤ 决定性：用 Mc 解 cont 加扰区，明文是否出现可读结构？")
print("=" * 88)
S, E = 0x1400, 0x19800
best = None
for ph in range(L):
    seg = cont[S:E]
    n = min(len(seg), 0x8000)
    p = bytes(seg[i] ^ Mc[(i + ph) % L] for i in range(n))
    ev = ent(p)
    if best is None or ev < best[0]:
        best = (ev, ph, p)
print("  最佳相位 %d  明文熵=%.4f" % (best[1], best[0]))
print("  解出的前 96B:", best[2][:96].hex())
print("  ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in best[2][:96]))
print()

print("=" * 88)
print("⑥ 同一相位下用 Ma 解，是否一致？")
print("=" * 88)
best2 = None
for ph in range(L):
    seg = cont[S:E]
    n = min(len(seg), 0x8000)
    p = bytes(seg[i] ^ Ma[(i + ph) % L] for i in range(n))
    ev = ent(p)
    if best2 is None or ev < best2[0]:
        best2 = (ev, ph, p)
print("  最佳相位 %d  明文熵=%.4f" % (best2[1], best2[0]))
print("  解出的前 96B:", best2[2][:96].hex())
print("  ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in best2[2][:96]))
