"""定性收口：GT7868Q 主体到底是「代码」「数据表」还是「还有一层」？

三项交叉检验：
 C1 非 0 部分熵对照 —— GT7868Q主体 vs TF100A(真代码) vs 随机
 C2 那些「解码后全 0」的段的【密文】是否 1024 周期（K 正确性的独立自洽检验）
 C3 「每 128 字节一条记录」结构 —— 若是，则为数据结构而非代码
"""
import os
import collections
import math
import random

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
K = open(os.path.join(HERE, "GT7868Q_scramble_key.bin"), "rb").read()
raw = open(os.path.join(HERE, "..", "..", "..", "..",
                        "Users", "<USER>", "WorkBuddy",
                        "2026-09-27-14-52-52", "fw-touchpad",
                        "touchpad_GT7868Q_fw.bin"), "rb").read() \
    if False else None

# 原始密文（用于 C2）
import glob
CAND = [r"<WORKSPACE>"]
raw = open(CAND[0], "rb").read()

GQ = d[0x1200:0x19800]
TF = d[0x19800:]
L = 1024


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


print("=" * 96)
print("C1 非 0 部分熵：GT7868Q主体 vs TF100A(确认代码) vs 随机对照")
print("=" * 96)
random.seed(9)
RND = bytes(random.randrange(256) for _ in range(len(GQ)))
for name, seg in (("GT7868Q主体", GQ), ("TF100A真代码", TF), ("随机字节", RND)):
    nz = bytes(x for x in seg if x != 0)
    nff = bytes(x for x in seg if x != 0xFF)
    print("  %-14s 全段熵 %.4f  非0熵 %.4f  非0xFF熵 %.4f  0x00占比 %.2f%%" % (
        name, ent(seg), ent(nz), ent(nff), 100 * seg.count(0) / len(seg)))
print()
print("  ★ SF100A 非0熵是「代码+数据表」的真实基准；GT7868Q 若远高于它 ⇒ 不是同类内容")
print()

print("=" * 96)
print("C2 自洽检验：解码后全 0 的段，其【原始密文】是否 1024 周期？")
print("   （若 P=0 且 C=P^K ⇒ C≡K ⇒ C 必须 1024 周期。这是 K 正确性的独立确认）")
print("=" * 96)
runs = [('0x036E0', 858), ('0x05630', 1034), ('0x082F0', 76), ('0x084F0', 5450),
        ('0x0B6FC', 64), ('0x0F600', 900)]
for label, ln in runs:
    s = int(label, 16)
    if s + ln > len(raw):
        continue
    cseg = raw[s:s + ln]
    pseg = GQ[s - 0x1200:s - 0x1200 + ln]
    z = 100 * pseg.count(0) / len(pseg)
    if ln > L:
        r = sum(1 for i in range(len(cseg) - L) if cseg[i] == cseg[i + L]) / (len(cseg) - L)
    else:
        r = None
    print("  %s 长 %5d  解码后0x00=%6.2f%%  密文1024周期一致性=%s" % (
        label, ln, z, ("%.6f" % r) if r is not None else "n/a(段短于1KiB)"))
print()

print("=" * 96)
print("C3 「每 128 字节一条记录」结构检验")
print("=" * 96)
if True:
    # 用 0 段的起点序列看周期性
    zpos = [i for i in range(len(GQ)) if GQ[i] == 0]
    # 找所有 >=32B 的 0 段起点
    starts = []
    cur = None
    for i, x in enumerate(GQ):
        if x == 0:
            if cur is None:
                cur = i
        else:
            if cur is not None and i - cur >= 32:
                starts.append(cur)
            cur = None
    deltas = collections.Counter(starts[i + 1] - starts[i] for i in range(len(starts) - 1))
    print("  0 段起点共 %d 个" % len(starts))
    print("  相邻间隔 Top 10: %s" % deltas.most_common(10))
    print()
    print("  → 若 128 反复出现 ⇒ 128 字节定长记录的「尾部填充」模式 ⇒ 数据结构，非代码")
print()

print("=" * 96)
print("C4 与 GT9896（同代固件）做「密文级」结构对照")
print("=" * 96)
anc = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()
print("  GT9896 长度 %d，GT7868Q 容器 %d" % (len(anc), len(d)))
print("  GT9896 四等分熵: %s" % " ".join("%.4f" % ent(anc[i * len(anc) // 4:(i + 1) * len(anc) // 4]) for i in range(4)))
print("  GT7868Q主体四等分熵: %s" % " ".join("%.4f" % ent(GQ[i * len(GQ) // 4:(i + 1) * len(GQ) // 4]) for i in range(4)))
print()
# GT9896 是否也有"每128字节0段"
a_runs = []
cur = None
for i, x in enumerate(anc):
    if x == 0:
        if cur is None:
            cur = i
    else:
        if cur is not None and i - cur >= 32:
            a_runs.append((cur, i - cur))
        cur = None
print("  GT9896 中 >=32B 的全 0 段（未解码，直接看密文）：%d 个" % len(a_runs))
print("    %s" % a_runs[:12])
