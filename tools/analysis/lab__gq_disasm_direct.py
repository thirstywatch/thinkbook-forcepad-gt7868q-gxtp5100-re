"""最后一轮直验：反汇编 GT7868Q 主体若干候选段，人眼判断 + BL 指令检验。

BL（Thumb 函数调用）是代码的显眼标志：高半字 0xF000-0xF7FF。
若 GT7868Q 主体是代码，BL 应在合理密度；若是数据，则接近随机的 8/256。
"""
import os
import collections
import random
import capstone
from capstone import *

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
GQ = d[0x1200:0x19800]
TF = d[0x19800:]
random.seed(11)
RND = bytes(random.randrange(256) for _ in range(len(GQ)))


def blrate(seg):
    """BL/BLX 高半字：0xF000-0xF7FF（第二个半字的第 5 位区分 BL/BLX）"""
    n = len(seg)
    c = sum(1 for i in range(0, n - 3, 2) if 0xF0 <= seg[i + 1] <= 0xF7)
    return 1000 * c / n


def wide32(seg):
    """32 位 Thumb 指令（高半字 11101/11110/11111）占比"""
    n = len(seg)
    c = sum(1 for i in range(0, n - 1, 2) if 0xE8 <= seg[i + 1] <= 0xFF)
    return 1000 * c / n


print("=" * 92)
print("① BL / 32 位指令密度（每 KB）—— 代码 vs 数据的判据")
print("=" * 92)
for name, seg in (("GT7868Q主体", GQ), ("TF100A真代码", TF), ("随机字节", RND)):
    print("  %-14s BL 高半字 %.1f/KB   32位指令 %.1f/KB" % (name, blrate(seg), wide32(seg)))
print()

print("=" * 92)
print("② 反汇编直验：GT7868Q 主体三个候选段")
print("=" * 92)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
for off, note in ((0x0C200, "全段最低熵 6.19"), (0x12000, "中段"), (0x16000, "后段")):
    print("  ── 主体偏移 0x%05X（%s）──" % (off, note))
    insns = list(md.disasm(d[off:off + 0xA0], 0x08000000 + off))
    for i in insns[:22]:
        print("     %08X  %-18s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
    print("     (共 %d 条 / %d 字节)" % (len(insns), 0xA0))
    print()

print("=" * 92)
print("③ 对照：TF100A 真代码同一格式（应一眼看出是代码）")
print("=" * 92)
for i in list(md.disasm(d[0x203C6:0x203C6 + 0x60], 0x0800BBC6))[:18]:
    print("     %08X  %-18s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
print()

print("=" * 92)
print("④ 「跳跃目标对齐」检验：反汇编后所有分支指令的目标地址 mod 2 == 0 的比例")
print("   （真代码：分支只能落在指令边界 ⇒ 100%；数据：随机 ⇒ ~50%）")
print("=" * 92)
import re
for name, seg, base in (("GT7868Q主体", GQ, 0x08001200), ("TF100A真代码", TF, 0x08005000)):
    ok = bad = 0
    for i in list(md.disasm(seg[:0x8000], base)):
        if i.mnemonic.startswith("b") and "#" in i.op_str:
            m = re.search(r"#(0x[0-9a-f]+)", i.op_str)
            if m:
                t = int(m.group(1), 16)
                if t % 2 == 0:
                    ok += 1
                else:
                    bad += 1
    tot = ok + bad
    print("  %-14s 分支指令 %4d 条，目标偶对齐 %4d (%.1f%%)" % (
        name, tot, ok, 100 * ok / max(1, tot)))
