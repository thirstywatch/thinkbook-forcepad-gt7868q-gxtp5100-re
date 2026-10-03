"""全架构反汇编评分：GT7868Q 主体（0x1200-0x19800）到底是什么 CPU？

标定基准：TF100A 段（0x19800+）已确认是 Cortex-M4F(Thumb-2)，
          同一流程下它应给出"高覆盖率 + 低伪指令率"。
          用这个基准去校准其它架构的评分尺度。
"""
import os
import collections
import capstone
from capstone import *

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()

GQ = d[0x1200:0x1200 + 0x8000]
TF = d[0x19800:0x19800 + 0x8000]

def _m(name, default=0):
    return getattr(capstone, name, default)


MODES = [
    ("ARM", CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN),
    ("Thumb", CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN),
    ("Thumb+V8", CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN | CS_MODE_V8),
    ("ARM64/A64", CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN),
    ("MIPS32LE", CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN),
    ("MIPS32BE", CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_BIG_ENDIAN),
    ("RISCV32LE", CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_LITTLE_ENDIAN),
    ("PPC32LE", CS_ARCH_PPC, CS_MODE_32 | CS_MODE_LITTLE_ENDIAN),
    ("SH4LE", CS_ARCH_SH, _m("CS_MODE_SH4") | CS_MODE_LITTLE_ENDIAN),
    ("TRICORE", CS_ARCH_TRICORE, _m("CS_MODE_TRICORE_162", 0)),
    ("M68K", CS_ARCH_M68K, CS_MODE_BIG_ENDIAN),
    ("MOS65XX", CS_ARCH_MOS65XX, 0),
    ("XCore", CS_ARCH_XCORE, CS_MODE_BIG_ENDIAN),
    ("SYSZ", CS_ARCH_SYSZ, CS_MODE_BIG_ENDIAN),
]


def score(arch, mode, code, base=0):
    try:
        md = Cs(arch, mode)
        md.skipdata = True
        insns = list(md.disasm(code, base))
    except Exception as e:
        return None
    if not insns:
        return (0.0, 0.0, 0.0, 0)
    total = len(code)
    covered = sum(i.size for i in insns)
    fake = sum(1 for i in insns if i.mnemonic.startswith(".") or i.mnemonic in ("udf", "undefined", "invalid"))
    return (covered / total, fake / len(insns), len(insns) / (total / 1024), len(insns))


print("=" * 96)
print("① 标定：TF100A 段（确认 Cortex-M4F/Thumb-2）—— 找「正确架构」该长什么样")
print("=" * 96)
print("  %-18s %-10s %-10s %-10s" % ("架构", "覆盖率", "伪指令率", "条/KB"))
for name, a, m in MODES:
    r = score(a, m, TF, 0x08005000)
    if r is None:
        print("  %-18s （不支持）" % name)
        continue
    print("  %-18s %-10.1f%% %-10.1f%% %-10.1f" % (name, 100 * r[0], 100 * r[1], r[2]))
print()

print("=" * 96)
print("② 待测：GT7868Q 主体（0x1200-0x9800）")
print("=" * 96)
rows = []
for name, a, m in MODES:
    r = score(a, m, GQ, 0x08001200)
    if r is None:
        print("  %-18s （不支持）" % name)
        continue
    rows.append((r[0] - r[1], name, r))
    print("  %-18s 覆盖率 %-10.1f%% 伪指令率 %-10.1f%% %-10.1f 条/KB" % (
        name, 100 * r[0], 100 * r[1], r[2]))
print()
rows.sort(reverse=True)
print("  → 综合（覆盖率−伪指令率）最高：%s" % rows[0][1] if rows else "")
print()

print("=" * 96)
print("③ 关键对比：同一架构下 TF100A（已知代码） vs GT7868Q 主体")
print("=" * 96)
print("  %-18s %-22s %-22s" % ("架构", "TF100A(应高)", "GT7868Q主体"))
for name, a, m in MODES[:6]:
    r1 = score(a, m, TF, 0x08005000)
    r2 = score(a, m, GQ, 0x08001200)
    if r1 is None or r2 is None:
        continue
    print("  %-18s 覆盖%5.1f%% 伪%5.1f%%      覆盖%5.1f%% 伪%5.1f%%" % (
        name, 100 * r1[0], 100 * r1[1], 100 * r2[0], 100 * r2[1]))
print()

print("=" * 96)
print("④ 新假设检验：GT7868Q 主体是不是「16 位字组织的表」而非代码？")
print("=" * 96)
# 若主体是 16 位表：偶字节与奇字节的分布应不同；且相邻字之间有关联
for label, seg in (("GT7868Q 主体", d[0x1200:0x19800]), ("TF100A", d[0x19800:])):
    even = seg[0::2]
    odd = seg[1::2]
    c16 = collections.Counter(seg[i] | (seg[i + 1] << 8) for i in range(0, len(seg) - 1, 2))
    tot16 = len(seg) // 2
    # 「相同 16 位字」的重复度
    dup = sum(v - 1 for v in c16.values())
    print("  %-14s 奇/偶字节熵差 %.4f   16位字去重率 %.1f%%   最高频字 %s" % (
        label, abs(collections.Counter(even).__len__() - collections.Counter(odd).__len__()),
        100 * (1 - len(c16) / tot16),
        "0x%04X×%d" % max(c16.items(), key=lambda kv: kv[1])))
print()

print("=" * 96)
print("⑤ 假设检验：是否是「32 位字」且高字节恒为某值（DSP/FPGA 常见）")
print("=" * 96)
for label, seg in (("GT7868Q 主体", d[0x1200:0x19800]), ("TF100A", d[0x19800:])):
    b = [seg[i] for i in range(3, len(seg), 4)]
    print("  %-14s 每 4 字节第 4 字节：熵 %.3f  众数 0x%02X(%.1f%%)" % (
        label, 0 if not b else -sum((v / len(b)) * __import__("math").log2(v / len(b))
                                    for v in collections.Counter(b).values()),
        collections.Counter(b).most_common(1)[0][0],
        100 * collections.Counter(b).most_common(1)[0][1] / len(b)))
