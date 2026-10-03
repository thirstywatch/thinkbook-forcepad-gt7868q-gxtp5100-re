"""在 TF100A 的【真 Cortex-M4F 代码】里搜触觉（AW86927 / LRA）线索。

为什么转到 TF100A：
  - 它是本容器内唯一「可确认 + 可反汇编」的代码（57180 B，Thumb-2，伪指令率 0.2%）
  - 项目既有结论：TF100A 的 PA3 可能连到 AW86927 的 TRIG1（硬件触发线）
  - GT7868Q 主体经检验不是可反汇编代码（非 Thumb / 非重排 Thumb / 特征密度≤随机）

搜索项：
 T1 I²C 从机地址常量：0x5A / 0x5B / 0xB4-B7（AW86927 候选）
 T2 I²C 外设寄存器基址（从 movw/movt 配对里提取）
 T3 GPIO 位操作（PA3 = TRIG1 假设）
 T4 波形/时长相关常量
 T5 全部「MOVS rX,#imm8」立即数直方图（挑出非通用值）
"""
import os
import re
import collections
import capstone
from capstone import *

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()

# TF100A 段：文件偏移 0x19800 ↔ 地址 0x08005000（由 asm.txt 首行推得）
TF_OFF, TF_ADDR = 0x19800, 0x08005000
TF = d[TF_OFF:]
print("TF100A 段：文件偏移 0x%05X，长度 %d B，映射地址 0x%08X 起" % (TF_OFF, len(TF), TF_ADDR))
print()

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True

# 全量反汇编
insns = []
for i in md.disasm(TF, TF_ADDR):
    insns.append(i)
print("反汇编得到 %d 条指令" % len(insns))
mn = collections.Counter(i.mnemonic for i in insns)
print("Top 25 助记符: %s" % ", ".join("%s×%d" % (k, v) for k, v in mn.most_common(25)))
print()

print("=" * 96)
print("T1 「MOVS rX, #imm8」里的 I²C 地址候选（AW86927）")
print("=" * 96)
imm_hist = collections.Counter()
for i in insns:
    if i.mnemonic in ("movs", "mov.w", "mov") and i.op_str.startswith("r") and "#" in i.op_str:
        m = re.search(r"#(0x[0-9a-f]+|\d+)", i.op_str)
        if m:
            v = int(m.group(1), 16) if m.group(1).startswith("0x") else int(m.group(1))
            imm_hist[v & 0xFF] += 1
for val, desc in [(0x5A, "AW86927 地址A"), (0x5B, "地址B"), (0xB4, "0x5A<<1"),
                  (0xB5, "0x5A<<1|1"), (0xB6, "0x5B<<1"), (0xB7, "0x5B<<1|1"),
                  (0x58, "TF100A OAR1=0x58"), (0x2C, "触控板 0x2C")]:
    print("  0x%02X (%-16s) 出现 %3d 次" % (val, desc, imm_hist.get(val, 0)))
print()
print("  立即数直方图 Top 30（找非通用值）:")
for v, c in imm_hist.most_common(30):
    print("     #0x%02X  ×%d" % (v, c))
print()

print("=" * 96)
print("T2 「MOVW+MOVT」配对提取的 32 位常量（外设基址 / 表地址）")
print("=" * 96)
pairs = []
for idx, i in enumerate(insns):
    if i.mnemonic == "movw" and "#" in i.op_str:
        m1 = re.search(r"(r\d+), #(0x[0-9a-f]+|\d+)", i.op_str)
        if not m1:
            continue
        reg, lo = m1.group(1), int(m1.group(2), 16) if m1.group(2).startswith("0x") else int(m1.group(2))
        # 往后找 3 条内同寄存器 mov t
        for j in range(idx + 1, min(idx + 4, len(insns))):
            j2 = insns[j]
            if j2.mnemonic == "movt" and j2.op_str.startswith(reg + ","):
                m2 = re.search(r"#(0x[0-9a-f]+|\d+)", j2.op_str)
                if m2:
                    hi = int(m2.group(1), 16) if m2.group(1).startswith("0x") else int(m2.group(1))
                    pairs.append((i.address, (hi << 16) | lo))
                break
print("  共提取 %d 个 32 位常量" % len(pairs))
c = collections.Counter(v for _, v in pairs)
print("  最常见的 20 个:")
for v, n in c.most_common(20):
    tag = ""
    if 0x40000000 <= v < 0x50000000:
        tag = " ← 外设区"
    elif 0x20000000 <= v < 0x30000000:
        tag = " ← SRAM"
    elif 0x08000000 <= v < 0x09000000:
        tag = " ← Flash"
    print("    0x%08X  ×%d%s" % (v, n, tag))
print()

print("=" * 96)
print("T3 GPIO 位操作（PA3 → TRIG1 假设）")
print("=" * 96)
gpio = [i for i in insns if i.mnemonic in ("str", "strb", "strh", "ldr", "ldrb", "ldrh")
        and ("0x400" in i.op_str or "0x500" in i.op_str)]
print("  含 0x400/0x500 偏移的 load/store：%d 条" % len(gpio))
for i in gpio[:20]:
    print("     %08X  %-8s %s" % (i.address, i.mnemonic, i.op_str))
print()

print("=" * 96)
print("T4 字符串（TF100A 段里最后再确认一次）")
print("=" * 96)
ss = re.findall(rb"[\x20-\x7e]{6,}", TF)
print("  ≥6 可打印串 %d 条，前 30：" % len(ss))
for s in ss[:30]:
    print("     @0x%05X %s" % (TF_OFF + TF.find(s), s.decode("latin-1")[:70]))
