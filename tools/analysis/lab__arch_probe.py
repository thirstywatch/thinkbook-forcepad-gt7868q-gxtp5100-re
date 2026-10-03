"""架构探测 + 反汇编质量评估：GT7868Q 明文固件到底是什么 CPU？

方法 A（无需工具）：搜函数序言/尾声特征模式
  Thumb  : BX LR = 70 47 ; PUSH {..,LR} = B5 Fx ; POP {..,PC} = BD Fx
  ARM32  : BX LR = 1E FF 2F E1 ; PUSH = xx xx 2D E9 ; POP = xx xx BD E8
  MIPS   : JR RA = 08 00 E0 03
方法 B（capstone）：多架构反汇编同一段，比"有效指令占比 / 助记符分布"
"""
import os
import collections
import capstone
from capstone import *

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
n = len(d)

print("=" * 92)
print("① 函数特征模式搜索（全文件）")
print("=" * 92)
pats = {
    "Thumb BX LR  (70 47)": b"\x70\x47",
    "Thumb PUSH   (B5 Fx)": None,
    "Thumb POP    (BD Fx)": None,
    "ARM  BX LR  (1E FF 2F E1)": b"\x1e\xff\x2f\xe1",
    "MIPS JR RA  (08 00 E0 03)": b"\x08\x00\xe0\x03",
}
c = d.count(pats["Thumb BX LR  (70 47)"])
print("  %-30s %5d 处" % ("Thumb BX LR  (70 47)", c))
c = d.count(pats["ARM  BX LR  (1E FF 2F E1)"])
print("  %-30s %5d 处" % ("ARM  BX LR  (1E FF 2F E1)", c))
c = d.count(pats["MIPS JR RA  (08 00 E0 03)"])
print("  %-30s %5d 处" % ("MIPS JR RA  (08 00 E0 03)", c))

# B5 Fx / BD Fx  —— 只在偶地址才可能是 Thumb 指令
b5 = [i for i in range(0, n - 1, 2) if d[i] == 0xB5 and (d[i + 1] & 0xF8) == 0xF0]
bd = [i for i in range(0, n - 1, 2) if d[i] == 0xBD and (d[i + 1] & 0xF8) == 0xF0]
print("  %-30s %5d 处（偶对齐）" % ("Thumb PUSH  (B5 Fx)", len(b5)))
print("  %-30s %5d 处（偶对齐）" % ("Thumb POP   (BD Fx)", len(bd)))
b5a = [i for i in range(0, n - 1) if d[i] == 0xB5]
bda = [i for i in range(0, n - 1) if d[i] == 0xBD]
print("     （不限对齐：B5 %d 处 / BD %d 处）" % (len(b5a), len(bda)))
print()

print("=" * 92)
print("② 明文头里的 4 个同构块（0x40000000 出现于 0x3F0/0x82C/0xC68/0x10A4，间隔 0x43C）")
print("=" * 92)
for k in range(4):
    off = 0x3F0 + k * 0x43C
    print("  块 %d @0x%05X :" % (k, off), d[off - 16:off + 32].hex())
print()
print("  块起始（往上找边界）0x0000 / 0x043C / 0x0878 / 0x0CB4 ?")
for k in range(5):
    off = k * 0x43C
    if off + 32 <= len(d):
        print("    0x%05X : %s" % (off, d[off:off + 32].hex()))
print()

print("=" * 92)
print("③ 多架构反汇编质量对比（样段：0x1200 起 8 KiB）")
print("=" * 92)
SAMPLE = d[0x1200:0x1200 + 0x2000]
BASE = 0x1200

cands = [
    ("Thumb", CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN),
    ("ARM32", CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN),
    ("MIPS32LE", CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN),
    ("RISCV32", CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_LITTLE_ENDIAN),
    ("Xtensa", CS_ARCH_XTENSA, CS_MODE_LITTLE_ENDIAN),
]
for name, arch, mode in cands:
    try:
        md = Cs(arch, mode)
        md.skipdata = True
        insns = list(md.disasm(SAMPLE, BASE))
    except Exception as e:
        print("  %-10s 不支持：%s" % (name, e))
        continue
    if not insns:
        print("  %-10s 反汇编 0 条" % name)
        continue
    mn = collections.Counter(i.mnemonic for i in insns)
    # 覆盖率 = 指令覆盖的字节 / 总字节
    cover = sum(i.size for i in insns) / len(SAMPLE)
    # 数据伪指令占比
    datalike = sum(v for k, v in mn.items() if k in (".byte", ".short", ".word")) / len(insns)
    top = ", ".join("%s×%d" % (k, v) for k, v in mn.most_common(8))
    print("  %-10s 指令 %5d 条  覆盖 %.1f%%  伪指令 %.1f%%" % (name, len(insns), 100 * cover, 100 * datalike))
    print("             Top: %s" % top)
print()

print("=" * 92)
print("④ 若为 Thumb：看 0x1200 起的反汇编实际长相")
print("=" * 92)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
for i in list(md.disasm(d[0x1200:0x1280], 0x1200))[:40]:
    print("  0x%05X: %-8s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
