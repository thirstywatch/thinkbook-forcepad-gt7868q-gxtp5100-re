"""排除性实验：解出的主体是"真明文"还是"仍带字节级后处理"？

逻辑：若 K 正确但存在第二层（如位反转、字内字节交换），
      则解出的数据不可读，但 0 区仍为 0（0 在多数变换下不变）。
      对每种候选变换做后处理，再看可读字符串/熵是否显著改善。
"""
import os
import re
import collections
import math

HERE = os.path.dirname(os.path.abspath(__file__))
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
seg = d[0x1200:0x19800]


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


def score(b):
    """可读性评分：ASCII 串数量 + 字母占比"""
    ss = re.findall(rb"[\x20-\x7e]{6,}", b)
    letters = sum(1 for x in b if 65 <= x <= 90 or 97 <= x <= 122)
    return len(ss), letters / len(b)


BR = bytes(int(format(i, "08b")[::-1], 2) for i in range(256))


def bswap16(b):
    out = bytearray(b)
    for i in range(0, len(b) - 1, 2):
        out[i], out[i + 1] = b[i + 1], b[i]
    return bytes(out)


def breverse4(b):
    return b"".join(b[i:i + 4][::-1] for i in range(0, len(b) - 3, 4))


print("=" * 88)
print("基线（当前解出结果）")
print("=" * 88)
n, lr = score(seg)
print("  熵=%.4f  字符串(≥6)=%d  字母占比=%.4f" % (ent(seg), n, lr))
print()

print("=" * 88)
print("候选后处理与其效果")
print("=" * 88)
variants = {
    "原样": lambda b: b,
    "字节位反转(bitrev)": lambda b: b.translate(BR),
    "16位字内字节交换": bswap16,
    "32位字内字节反转": breverse4,
    "逐字节取反(~b)": lambda b: bytes(x ^ 0xFF for x in b),
    "16位字取反": lambda b: bytes(x ^ 0xFF for x in b),
}
rows = []
for name, fn in variants.items():
    v = fn(seg)
    s, l = score(v)
    rows.append((s, name, ent(v), l))
    print("  %-20s 字符串=%-4d 熵=%.4f 字母占比=%.4f" % (name, s, ent(v), l))
print()
best = max(rows)
print("  最佳：%s（字符串 %d 条）" % (best[1], best[0]))
print()

print("=" * 88)
print("★ 分块熵剖面：解出的主体里，是否存在「低熵块」被高熵块夹击？")
print("=" * 88)
print("  （若正确，固件应有：代码块 6.0-6.8 / 数据表块 4-6 / 填充块 ~0）")
hist = collections.Counter()
for i in range(0, len(seg) - 512, 512):
    e = ent(seg[i:i + 512])
    if e < 1: hist["0-1 (填充)"] += 1
    elif e < 4: hist["1-4 (稀疏表)"] += 1
    elif e < 6: hist["4-6 (数据表)"] += 1
    elif e < 7: hist["6-7 (代码)"] += 1
    elif e < 7.6: hist["7-7.6"] += 1
    else: hist["7.6-8 (高熵)"] += 1
tot = sum(hist.values())
for k in ("0-1 (填充)", "1-4 (稀疏表)", "4-6 (数据表)", "6-7 (代码)", "7-7.6", "7.6-8 (高熵)"):
    v = hist.get(k, 0)
    print("  %-16s %5d 块  %5.1f%%  %s" % (k, v, 100 * v / tot, "#" * int(60 * v / tot)))
print()

print("=" * 88)
print("★ 关键对照：TF100A 段（同文件内的【未加扰明文】）的同类剖面")
print("=" * 88)
tf = d[0x19A00:]
hist2 = collections.Counter()
for i in range(0, len(tf) - 512, 512):
    e = ent(tf[i:i + 512])
    if e < 1: hist2["0-1 (填充)"] += 1
    elif e < 4: hist2["1-4 (稀疏表)"] += 1
    elif e < 6: hist2["4-6 (数据表)"] += 1
    elif e < 7: hist2["6-7 (代码)"] += 1
    elif e < 7.6: hist2["7-7.6"] += 1
    else: hist2["7.6-8 (高熵)"] += 1
tot2 = sum(hist2.values())
for k in ("0-1 (填充)", "1-4 (稀疏表)", "4-6 (数据表)", "6-7 (代码)", "7-7.6", "7.6-8 (高熵)"):
    v = hist2.get(k, 0)
    print("  %-16s %5d 块  %5.1f%%  %s" % (k, v, 100 * v / tot2, "#" * int(60 * v / tot2)))
