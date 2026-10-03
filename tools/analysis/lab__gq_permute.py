"""最终翻盘尝试：GT7868Q 主体是否只是「字节重排/交织」导致反汇编失败？

若真代码被以某种固定方式重排（16 位交换 / 32 位重排 / 去交织），
则"逆重排"后 Thumb 指令特征（PUSH/POP/BXLR/MOVW/LDR_PC）密度应显著上升。
以 TF100A（无序重排的真代码）为上限参照，随机数据为下限参照。
"""
import os
import collections
import random

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
GQ = d[0x1200:0x19800]
TF = d[0x19800:]


def feats(seg):
    n = len(seg)
    if n < 2048:
        return None
    ldrpc = sum(1 for i in range(n - 1) if 0x48 <= seg[i + 1] <= 0x4F)
    push = sum(1 for i in range(n - 1) if seg[i] in (0xB4, 0xB5) and seg[i + 1] & 1 == 0)
    pop = sum(1 for i in range(n - 1) if seg[i] in (0xBC, 0xBD))
    bxlr = seg.count(b"\x70\x47")
    movw = sum(1 for i in range(n - 1) if 0x40 <= seg[i] <= 0x4F and seg[i + 1] == 0xF2)
    k = n / 1024
    return (ldrpc / k, push / k, pop / k, bxlr / k, movw / k)


def bswap16(b):
    o = bytearray(b)
    for i in range(0, len(b) - 1, 2):
        o[i], o[i + 1] = b[i + 1], b[i]
    return bytes(o)


def brev4(b):
    return b"".join(b[i:i + 4][::-1] for i in range(0, len(b) - 3, 4))


def deint(b, k, ch):
    return bytes(b[i] for i in range(ch, len(b), k))


random.seed(3)
RND = bytes(random.randrange(256) for _ in range(len(GQ)))

variants = [
    ("原样", GQ),
    ("16位字内交换", bswap16(GQ)),
    ("32位字内反转", brev4(GQ)),
    ("去交织 k=2 ch0", deint(GQ, 2, 0)),
    ("去交织 k=2 ch1", deint(GQ, 2, 1)),
    ("去交织 k=4 ch0", deint(GQ, 4, 0)),
    ("去交织 k=4 ch2", deint(GQ, 4, 2)),
]
refs = [("TF100A真代码", TF), ("随机字节", RND)]

print("=" * 100)
print("指令特征密度（每 KB）—— 参照系在前")
print("=" * 100)
print("  %-18s %-9s %-9s %-9s %-9s %-9s" % ("样本", "LDR_PC", "PUSH", "POP", "BXLR", "MOVW"))
for name, seg in refs:
    f = feats(seg)
    print("  ★ %-16s %-9.1f %-9.1f %-9.1f %-9.1f %-9.1f" % (name, *f))
print("  " + "-" * 84)
for name, seg in variants:
    f = feats(seg)
    if f is None:
        print("  %-18s （太短）" % name)
        continue
    print("    %-16s %-9.1f %-9.1f %-9.1f %-9.1f %-9.1f" % (name, *f))
print()

print("=" * 100)
print("综合评分：5 个特征中，超过「随机字节」参照的个数")
print("=" * 100)
rnd_f = feats(RND)
tf_f = feats(TF)
for name, seg in variants:
    f = feats(seg)
    if f is None:
        continue
    better_than_rnd = sum(1 for a, b in zip(f, rnd_f) if a > b)
    ratio = sum(a / max(b, 1e-9) for a, b in zip(f, rnd_f)) / 5
    print("  %-18s 超过随机: %d/5   与随机之比均值 %.2f" % (name, better_than_rnd, ratio))
print()
print("  判读：若某重排让『超过随机』达 4-5 项且比均值 > 1.5 ⇒ 找到正确的重排")
print("       若全部 ≈ 原地 ⇒ GT7868Q 主体既非 Thumb 代码、也不是简单重排的 Thumb 代码")
