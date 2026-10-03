"""步骤13：收尾核查
(A) I2C1 helper 簇与驱动簇的完整寄存器访问清单（含 CR1/CR2/SR1/SR2/DR/OAR1/CCR/TRISE）
(B) 12 个 I2C1 基址点之后是否有 str 把基址写进 RAM（防止间接传递）
(C) bit-band 别名常量扫描（0x42xxxxxx / 0x22xxxxxx / 0x43xxxxxx）
(D) GPIO helper 调用点之后是否有循环（bit-bang 需要重复翻转）
(E) DMA 基址是否被当作参数传递（而不是只用于 cmp）
(F) I2C1 初始化函数 0x08008B68 的调用者
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

ASM = os.path.join(ROOT, "touchpad_TF100A_thumb.asm.txt")
rows = []
for l in open(ASM, encoding="utf-8"):
    p = l.rstrip().split(None, 2)
    if len(p) < 2:
        continue
    try:
        pc = int(p[0], 16)
    except ValueError:
        continue
    rows.append((pc, p[1], p[2] if len(p) > 2 else ""))
IDX = {r[0]: k for k, r in enumerate(rows)}

data = seg()
m = md()

REG = {0x00: "CR1", 0x04: "CR2", 0x08: "OAR1", 0x0C: "OAR2", 0x10: "DR",
       0x14: "SR1", 0x18: "SR2", 0x1C: "CCR", 0x20: "TRISE"}

print("=== (A1) SPL I2C 簇 0x0800F9CC-0x0800FD64 的完整指令清单（带 I2C 寄存器注释）===")
a = 0x0800F9CC
while a <= 0x0800FD64:
    i = insn_at(m, data, a)
    if i is None:
        print("  0x%08X <undecodable>" % a); a += 2; continue
    memo = ""
    if i.mnemonic.startswith("str") or i.mnemonic.startswith("ldr"):
        mo = re.search(r"\[(\w+)(?:,\s*#(0x[0-9a-fA-F]+))?\]", i.op_str)
        if mo and mo.group(1) not in ("sp", "pc"):
            off = int(mo.group(2), 16) if mo.group(2) else 0
            if off in REG:
                memo = "   ; I2C1->%s" % REG[off]
            elif off >= 0x90:
                memo = "   ; base+0x%X (非 I2C 寄存器)" % off
    print("  0x%08X  %-9s %-32s%s" % (a, i.mnemonic, i.op_str, memo))
    a += i.size

print("\n=== (A2) 驱动簇 0x0800894C-0x08008C32 中所有访问 0x40005400 的指令 ===")
for pc, mn, ops in rows:
    if not (0x0800894C <= pc <= 0x08008C32):
        continue
    # 找出 movw #0x5400/0x5410/0x5414 之后 12 条内的寄存器访问
    pass
for lo, hi in [(0x08008A60, 0x08008A6E), (0x08008A98, 0x08008ABE), (0x08008AC0, 0x08008AD2),
               (0x08008AEC, 0x08008B18), (0x08008B58, 0x08008B66), (0x08008B88, 0x08008C30)]:
    for pc, mn, ops in rows:
        if lo <= pc <= hi:
            print("  0x%08X  %-9s %s" % (pc, mn, ops))
    print("  ---")

print("\n=== (B) 12 个 I2C1 基址点之后 24 条内是否有把该寄存器存入内存的 str ===")
sites = [0x0800894E, 0x0800897A, 0x080089A2, 0x080089CA, 0x080089F2, 0x08008A34,
         0x08008A60, 0x08008A98, 0x08008AC0, 0x08008AEC, 0x08008B58, 0x08008B88]
for s in sites:
    k = IDX[s]
    reg = rows[k][2].split(",")[0]
    hit = []
    for j in range(k, min(len(rows), k + 24)):
        pc, mn, ops = rows[j]
        if mn.startswith("str") and re.match(r".*\[(sp|\w+)[^\]]*\]", ops) and re.search(r"\b%s\b" % reg, ops.split(",")[0]):
            if "[sp" in ops or re.search(r"\[r\d+", ops):
                tgt = re.search(r"\[(\w+)", ops).group(1)
                if tgt not in ("sp",):
                    hit.append((pc, mn, ops))
    print("  0x%08X (reg %s): %s" % (s, reg, hit if hit else "无 -> 基址未写入 RAM"))

print("\n=== (C) bit-band 别名 / 0x42xxxxxx / 0x43xxxxxx / 0x22xxxxxx 常量或字面量 ===")
n = 0
for o in range(0, len(data) - 3, 2):
    aa = SEG_LO + o
    i = insn_at(m, data, aa)
    if i is None:
        continue
    mm = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)$", i.op_str)
    if mm and i.mnemonic in ("movw",):
        lo16 = int(mm.group(1), 16)
        j = insn_at(m, data, aa + 4)
        if j and j.mnemonic == "movt":
            mm2 = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)$", j.op_str)
            if mm2:
                v = (int(mm2.group(1), 16) << 16) | lo16
                if 0x42000000 <= v < 0x44000000 or 0x22000000 <= v < 0x24000000:
                    print("  0x%08X 常量 0x%08X" % (aa, v)); n += 1
print("  合计 %d" % n)

print("\n=== (D) GPIO helper 调用点之后的 3 条指令（看是否有循环/bx）===")
for tgt in ("0x800f7fc", "0x800f80c"):
    for pc, mn, ops in rows:
        if mn in ("bl", "blx") and ops == "#" + tgt:
            k = IDX[pc]
            tail = ["%s %s" % (rows[j][1], rows[j][2]) for j in range(k + 1, min(len(rows), k + 4))]
            print("  0x%08X -> %s" % (pc, " | ".join(tail)))

print("\n=== (E) 0x40020000/0x40020400 是否被当参数传递 ===")
for pc, mn, ops in rows:
    if mn == "movw" and ops == "r0, #0x0" or ops == "r0, #0x2000":
        pass
for pc, mn, ops in rows:
    if mn == "movt" and ops in ("r0, #0x4002", "r1, #0x4002", "r2, #0x4002", "r3, #0x4002"):
        k = IDX[pc]
        for j in range(k + 1, min(len(rows), k + 6)):
            print("  0x%08X 之后: 0x%08X %s %s" % (pc, rows[j][0], rows[j][1], rows[j][2]))

print("\n=== (F) 0x08008B68（I2C slave init）的调用者 ===")
for pc, mn, ops in rows:
    if mn in ("bl", "blx", "b.w") and ops in ("#0x8008b68",):
        k = IDX[pc]
        print("  调用点 0x%08X" % pc)
        for j in range(max(0, k - 12), k + 1):
            print("      0x%08X  %-8s %s" % rows[j])
