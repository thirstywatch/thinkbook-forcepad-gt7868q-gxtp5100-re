# -*- coding: utf-8 -*-
"""
round25_i2c_proof.py —— 严格版：只有「基址寄存器确实等于 I2C1 基址」才算 I2C 访问
修正 round23/24 的 bug：此前用 mem.disp 匹配寄存器偏移，导致 [sp,#0]/[r1,#0] 误判为 CR1。
本版要求：基址寄存器在本函数内被装载过 I2C1 基址(0x40005400) 且未被改写。
输出: cfg_parsed/round25_i2c_proof.txt
"""
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round25_i2c_proof.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
L = []
def w(s=""):
    L.append(str(s)); print(s, flush=True)

D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = True

I2C1 = 0x40005400
I2C_REGS = {0x00: "CR1", 0x04: "CR2", 0x08: "OAR1", 0x0C: "OAR2",
            0x10: "DR", 0x14: "SR1", 0x18: "SR2", 0x1C: "CCR", 0x20: "TRISE"}

w("=" * 78)
w("round25 —— 严格版 I2C 访问判定（基址必须 == 0x40005400）")
w("=" * 78)
w("")

SEG_LO, SEG_HI = 0x1D300, 0x1DA80
insns = list(md.disasm(D[SEG_LO:SEG_HI], BASE + SEG_LO))
w("反汇编 0x%05X-0x%05X -> %d 条指令, udf %d" %
  (SEG_LO, SEG_HI, len(insns), sum(1 for i in insns if i.mnemonic == "udf")))
w("")

# 跟踪：哪些寄存器持有 I2C1 基址
holds_i2c = set()
const = {}
accesses = []
data_src = {}

for ins in insns:
    fo = ins.address - BASE
    mn = ins.mnemonic
    ops = ins.operands

    # --- 更新「持有 I2C1 基址」的寄存器集合 ---
    # movw rX, #0x5400 ; movt rX, #0x4000
    if mn in ("mov", "movs", "mov.w") and len(ops) == 2 and ops[0].type == ARM_OP_REG:
        rd = ins.reg_name(ops[0].reg)
        if ops[1].type == ARM_OP_IMM and ops[1].imm == I2C1:
            holds_i2c.add(rd)
        elif ops[1].type == ARM_OP_REG:
            rs = ins.reg_name(ops[1].reg)
            if rs in holds_i2c:
                holds_i2c.add(rd)
            elif rd in holds_i2c:
                holds_i2c.discard(rd)
        else:
            if rd in holds_i2c:
                holds_i2c.discard(rd)
    elif mn == "movw" and len(ops) == 2 and ops[1].type == ARM_OP_IMM:
        rd = ins.reg_name(ops[0].reg)
        if rd in holds_i2c and (ops[1].imm & 0xFFFF) != (I2C1 & 0xFFFF):
            holds_i2c.discard(rd)
    elif mn == "movt" and len(ops) == 2 and ops[1].type == ARM_OP_IMM:
        rd = ins.reg_name(ops[0].reg)
        if rd in holds_i2c and (ops[1].imm & 0xFFFF) != (I2C1 >> 16):
            holds_i2c.discard(rd)
    elif mn in ("add", "sub", "orr", "and", "eor", "bic", "lsl", "lsr", "asr", "ror") and len(ops) >= 2:
        if ops[0].type == ARM_OP_REG and ins.reg_name(ops[0].reg) in holds_i2c:
            holds_i2c.discard(ins.reg_name(ops[0].reg))
    elif mn == "ldr" and len(ops) == 2 and ops[0].type == ARM_OP_REG:
        # ldr rX, [pc, #imm] -> 字面量，检查是否 == I2C1
        rd = ins.reg_name(ops[0].reg)
        if ops[1].type == ARM_OP_MEM and ins.reg_name(ops[1].mem.base or 0) == "pc":
            lit = (ins.address + 4 - 2 if ins.address % 4 == 0 else ins.address + 4) + ops[1].mem.disp
            lfo = lit - BASE
            if 0 <= lfo <= len(D) - 4:
                v = int.from_bytes(D[lfo:lfo+4], "little")
                if v == I2C1:
                    holds_i2c.add(rd)
                else:
                    holds_i2c.discard(rd)
        else:
            holds_i2c.discard(rd)

    # --- 判定 I2C 访问 ---
    if mn.startswith(("str", "strb", "strh", "ldr", "ldrb", "ldrh")):
        if ops:
            memop = ops[-1]
            if memop.type == ARM_OP_MEM:
                b = memop.mem.base
                basereg = ins.reg_name(b) if b else None
                if basereg in holds_i2c:
                    off = memop.mem.disp
                    rn = I2C_REGS.get(off, "?0x%02X" % off)
                    is_write = mn.startswith("str")
                    src = ""
                    if is_write and ops[0].type == ARM_OP_IMM:
                        src = "imm 0x%X" % ops[0].imm
                    elif is_write and ops[0].type == ARM_OP_REG:
                        rs = ins.reg_name(ops[0].reg)
                        v = const.get(rs)
                        src = "%s=%s" % (rs, ("0x%X" % v) if v is not None else "?")
                    elif not is_write and ops[0].type == ARM_OP_REG:
                        src = "-> %s" % ins.reg_name(ops[0].reg)
                    accesses.append((fo, mn, basereg, off, rn, src, ins.op_str))

    # --- 定值传播（仅用于给 src 一个好数值） ---
    if mn in ("mov", "movs", "mov.w") and len(ops) == 2 and ops[0].type == ARM_OP_REG:
        rd = ins.reg_name(ops[0].reg)
        if ops[1].type == ARM_OP_IMM:
            const[rd] = ops[1].imm
        elif ops[1].type == ARM_OP_REG and ins.reg_name(ops[1].reg) in const:
            const[rd] = const[ins.reg_name(ops[1].reg)]
        else:
            const.pop(rd, None)
    elif mn == "movw" and len(ops) == 2 and ops[1].type == ARM_OP_IMM:
        const[ins.reg_name(ops[0].reg)] = ops[1].imm & 0xFFFF
    elif mn == "movt" and len(ops) == 2 and ops[1].type == ARM_OP_IMM:
        rd = ins.reg_name(ops[0].reg)
        const[rd] = (const.get(rd, 0) & 0xFFFF) | ((ops[1].imm & 0xFFFF) << 16)
    elif mn in ("orr", "add", "sub") and len(ops) == 2 and ops[0].type == ARM_OP_REG and ops[1].type == ARM_OP_IMM:
        rd = ins.reg_name(ops[0].reg)
        if rd in const:
            a, b = const[rd], ops[1].imm
            const[rd] = (a | b) if mn == "orr" else ((a + b) & 0xFFFFFFFF if mn == "add" else (a - b) & 0xFFFFFFFF)
        else:
            const.pop(rd, None)
    elif mn.startswith(("ldr", "ldrb", "ldrh")) and ops and ops[0].type == ARM_OP_REG:
        rd = ins.reg_name(ops[0].reg)
        if len(ops) == 2 and ops[1].type == ARM_OP_MEM and ins.reg_name(ops[1].mem.base or 0) == "pc":
            lit = (ins.address + 4 - 2 if ins.address % 4 == 0 else ins.address + 4) + ops[1].mem.disp
            lfo = lit - BASE
            if 0 <= lfo <= len(D) - 4:
                const[rd] = int.from_bytes(D[lfo:lfo+4], "little")
        else:
            const.pop(rd, None)
    else:
        # 其它指令可能改写目标寄存器 -> 保守清除
        if mn not in ("cmp", "cmn", "tst", "push", "pop", "b", "bl", "bx", "blx", "nop"):
            if ops and ops[0].type == ARM_OP_REG and mn not in ("str", "strb", "strh"):
                const.pop(ins.reg_name(ops[0].reg), None)

w("-" * 78)
w("### 严格判定的 I2C1 访问（共 %d 处）" % len(accesses))
w("-" * 78)
for fo, mn, br, off, rn, src, opstr in accesses:
    w("  0x%05X  %-24s  [%s,#0x%02X]=%-5s  %s" % (fo, opstr, br, off, rn, src))
w("")

nwrite = sum(1 for a in accesses if a[1].startswith("str"))
nread = len(accesses) - nwrite
w("写入 %d 处, 读取 %d 处" % (nwrite, nread))
drw = [a for a in accesses if a[3] == 0x10 and a[1].startswith("str")]
drr = [a for a in accesses if a[3] == 0x10 and not a[1].startswith("str")]
w("DR(0x10) 写 %d 处, 读 %d 处" % (len(drw), len(drr)))
for a in drw:
    w("      DR写 0x%05X  %s" % (a[0], a[5]))
for a in drr:
    w("      DR读 0x%05X  %s" % (a[0], a[5]))
w("")

# 从地址：写 CR2(0x04) 时的值 = 目标从地址（STM32 I2C 风格）
w("-" * 78)
w("### CR2 写入值（STM32 I2C 的从地址寄存器 —— 若为 I2C 主机模式，这里就是从地址）")
w("-" * 78)
for a in accesses:
    if a[3] in (0x04, 0x08, 0x0C) and a[1].startswith("str"):
        w("  0x%05X  [%s,#0x%02X]=%-5s  %s" % (a[0], a[2], a[3], a[4], a[5]))
w("")
w("⇒ 若 CR2/OAR1 从未被写入明确从地址 ⇒ 本文件不含 I2C 主机发起代码，")
w("   或从地址是运行时由参数传入（需看调用者）")
w("")
w("=" * 78)
w("round25 结束")
w("=" * 78)
open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("\n[saved] " + OUT)
