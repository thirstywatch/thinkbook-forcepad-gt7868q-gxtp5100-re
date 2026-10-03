"""★ 决定性实验：GT9896 明文固件能否作为 GT7868Q 加扰区的已知明文锚点？

原理（A③）：
  设 C = 本机加扰区密文，P = 锚点明文（GT9896 固件的一段），K = 周期 1024 的位置型 keystream
  若 C[i] = P[i+phase] ^ K[i % 1024]  则  X = C ^ P 应满足 X[i] == X[i+1024]（高频）
  反过来，若锚点与 C 无关，则 X 无 1024 周期性。

  但注意 GT9896 是【触屏】，GT7868Q 是【触控板】—— 两者是【同代不同型号】，
  明文内容【不可能逐字节相同】。所以直接异或不会是 K。
  真正有意义的检验只有两条：
    (a) 头部/常量区是否结构同源（YELSTO 位置、产品号、magic 常量）
    (b) 是否存在「一段完全相同的字节序列」可做锚点（哪怕只有 1 KiB）
  本脚本对 (a)(b) 都做。

另外还要在 GT9896 里找：
  - 它本身是否也被加扰（熵剖面）
  - 它和本机容器中【明文段】的重合度（明文段 0x0000-0x11FF 与 0x19A00+）
"""
import os
import re
import collections
import math

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))

cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()

print("本机容器(7868Q) : %d B" % len(cont))
print("锚点  (GT9896)  : %d B\n" % len(anchor))


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


# ── ① GT9896 自身是否加扰（熵剖面）──
print("=" * 78)
print("① GT9896 明文的熵剖面（每 1 KiB）—— 若全程 ~8.0 则它也是加扰的")
print("=" * 78)
for i in range(0, len(anchor), 0x4000):
    seg = anchor[i:i + 0x4000]
    if len(seg) < 512:
        break
    print("   0x%05X-0x%05X  熵=%.4f" % (i, i + len(seg), ent(seg)))
print()

# ── ② 头部结构对照 ──
print("=" * 78)
print("② 头部对照（本机明文段 与 GT9896 头部）")
print("=" * 78)
print("  本机 cont[0x0000:0x0040] :", " ".join("%02X" % x for x in cont[0:0x40]))
print("  GT9896 anchor[0x00:0x40] :", " ".join("%02X" % x for x in anchor[0:0x40]))
print()
print("  本机 ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in cont[0:0x40]))
print("  GT99 ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in anchor[0:0x40]))
print()

# YELSTO 在本机的位置
for name, d in (("本机 cont", cont), ("锚点 GT9896", anchor)):
    idx = d.find(b"YELSTO")
    print("  %-12s YELSTO 位于 0x%05X" % (name, idx))
print()

# ── ③ 找最长公共子串（≥32 B 才算有意义）──
print("=" * 78)
print("③ 锚点与本机容器的公共子串搜索（≥32 B 才有锚点价值）")
print("=" * 78)
best = []
SEG = 32
seen = {}
for i in range(0, len(anchor) - SEG, 4):
    seen.setdefault(anchor[i:i + SEG], []).append(i)
hits = []
for j in range(0, len(cont) - SEG):
    k = cont[j:j + SEG]
    if k in seen:
        hits.append((j, seen[k][0]))
print("  命中（32B 对齐）数：%d" % len(hits))
for j, i in hits[:15]:
    print("     cont[0x%05X] == anchor[0x%05X]  : %s" % (
        j, i, cont[j:j + 40].hex()))
if not hits:
    print("  （无任何 32 B 公共子串 —— 两个固件确实无关）")
print()

# ── ④ 强判据复测（预期为负，但记录数据）──
print("=" * 78)
print("④ 强判据复测：X = C ⊕ anchor[phase:phase+len(C)]  的 1024 周期性")
print("=" * 78)
S, E = 0x1200, 0x19800
C = cont[S:E]
L = 1024


def rep(x):
    n = len(x) - L
    if n <= 0:
        return 0.0
    return sum(1 for i in range(n) if x[i] == x[i + L]) / n


print("   基线（随机）= %.6f" % (1 / 256))
rows = []
for off in range(0, max(1, len(anchor) - 2 * L), 0x200):
    seg = anchor[off:off + len(C)]
    if len(seg) < 2 * L:
        break
    x = bytes(a ^ b for a, b in zip(C[:len(seg)], seg))
    rows.append((rep(x), off))
rows.sort(reverse=True)
for r, off in rows[:8]:
    print("   anchor off=0x%05X  1024周期一致性=%.6f (%5.1f×基线)" % (off, r, r / 0.0039))

print()
# ── ⑤ 产品号/常量对齐检查 ──
print("=" * 78)
print("⑤ GT9896 里出现的可打印串（前 40 条，≥6 字符）")
print("=" * 78)
ss = re.findall(rb"[\x20-\x7e]{6,}", anchor)
print("  共 %d 条" % len(ss))
for s in ss[:40]:
    print("    ", s.decode("latin-1")[:72])
