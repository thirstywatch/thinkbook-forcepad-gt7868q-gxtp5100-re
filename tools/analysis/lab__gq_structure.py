"""GT7868Q 主体最终定性：结构发现（记录长度 / 表 / 代码）

判据：
 S1 stride 自相关全扫（32..4096，步长 2）—— 找"定长记录"周期
 S2 128 字节记录检验：是否 128 字节块之间高度相似（表特征）
 S3 0 段边界的对齐粒度（4/8/16/32/64/128/256）—— 数据表通常按 2^n 对齐
 S4 与 TF100A(真代码) 同指标对照
"""
import os
import collections

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
GQ = d[0x1200:0x19800]
TF = d[0x19800:]


def selfcorr(seg, stride, cap=None):
    n = len(seg) - stride
    if n <= 0:
        return 0.0
    step = max(1, n // (cap or 40000))
    hit = tot = 0
    for i in range(0, n, step):
        tot += 1
        if seg[i] == seg[i + stride]:
            hit += 1
    return hit / tot


print("=" * 96)
print("S1 stride 自相关全扫（找「定长记录」周期；随机基线 0.0039）")
print("=" * 96)
print("  搜索范围 32..2048，只列 > 3× 基线的")
for name, seg in (("GT7868Q主体", GQ), ("TF100A真代码", TF)):
    peaks = []
    for s in range(32, 2049, 2):
        r = selfcorr(seg, s)
        if r > 0.012:
            peaks.append((r, s))
    peaks.sort(reverse=True)
    print("  --- %s ---" % name)
    for r, s in peaks[:14]:
        print("     stride %5d  相等率 %.5f  (%.1f× 基线)" % (s, r, r / 0.0039))
    if not peaks:
        print("     （无任何 stride 超过 3× 基线）")
print()

print("=" * 96)
print("S2 128 字节块相似度（定长记录检验）")
print("=" * 96)
for name, seg in (("GT7868Q主体", GQ), ("TF100A真代码", TF)):
    R = 128
    blocks = [seg[i:i + R] for i in range(0, len(seg) - R, R)]
    # 相邻块之间的相等率
    adj = []
    for i in range(len(blocks) - 1):
        eq = sum(1 for a, b in zip(blocks[i], blocks[i + 1]) if a == b) / R
        adj.append(eq)
    # 去重
    uniq = len(set(blocks))
    print("  %-14s 块数 %5d  唯一 %5d (%.1f%%)  相邻块平均相等率 %.5f  最大 %.5f" % (
        name, len(blocks), uniq, 100 * uniq / len(blocks),
        sum(adj) / len(adj), max(adj)))
print()

print("=" * 96)
print("S3 0 段边界的对齐粒度")
print("=" * 96)
for name, seg in (("GT7868Q主体", GQ), ("TF100A真代码", TF)):
    starts = []
    cur = None
    for i, x in enumerate(seg):
        if x == 0:
            if cur is None:
                cur = i
        else:
            if cur is not None:
                if i - cur >= 16:
                    starts.append((cur, i - cur))
                cur = None
    if not starts:
        print("  %-14s 无 >=16B 的 0 段" % name)
        continue
    align = collections.Counter()
    for s, ln in starts:
        for g in (4, 8, 16, 32, 64, 128, 256, 512, 1024):
            if s % g == 0:
                align[g] += 1
    print("  %-14s %d 个 0 段" % (name, len(starts)))
    print("     对齐计数: %s" % sorted(align.items()))
    lens = collections.Counter(ln for _, ln in starts)
    print("     长度分布 Top8: %s" % lens.most_common(8))
    # 段起点相对 128 的余数
    rem = collections.Counter(s % 128 for s, _ in starts)
    print("     起点 %% 128 的余数分布 Top6: %s" % rem.most_common(6))
print()

print("=" * 96)
print("S4 定论用：GT7868Q 主体的「16 位字」与「32 位字」重复度")
print("=" * 96)
for name, seg in (("GT7868Q主体", GQ), ("TF100A真代码", TF)):
    w16 = [seg[i] | (seg[i + 1] << 8) for i in range(0, len(seg) - 1, 2)]
    w32 = [seg[i] | (seg[i + 1] << 8) | (seg[i + 2] << 16) | (seg[i + 3] << 24)
           for i in range(0, len(seg) - 3, 4)]
    c16 = collections.Counter(w16); c32 = collections.Counter(w32)
    print("  %-14s 16位字: 唯一 %5d/%5d (%.1f%%)  32位字: 唯一 %6d/%6d (%.1f%%)" % (
        name, len(c16), len(w16), 100 * len(c16) / len(w16),
        len(c32), len(w32), 100 * len(c32) / len(w32)))
