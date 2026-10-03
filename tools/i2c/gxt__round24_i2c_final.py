# -*- coding: utf-8 -*-
"""
round24_i2c_final.py —— I2C 写路径的确证（用 capstone 自带 reg_name，不用手写枚举）
目标：找到 I2C1->DR(0x40005410) 的每次写入，其数据来源的**真实数值**。
      若能找到从地址，就能回答「触觉是否独立芯片」。
方法：
  1) 用 md.disasm 连续反汇编 0x1D300-0x1DA00（I2C 驱动主段）。
  2) 对每个 str/strb 写入 I2C 寄存器区(0x00-0x28) 的指令，
     用 capstone 的 operand.reg_name / mem.base 打印人类可读形式。
  3) 对数据源寄存器做定值传播（mov/movw/movt/ldr=literal），打印最终数值。
  4) 单独列出所有写入 DR 的路径，以及所有作为「从地址」候选的立即数。
输出: cfg_parsed/round24_i2c_final.txt
"""
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round24_i2c_final.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
L = []
def w(s=""):
    L.append(str(s)); print(s, flush=True)

D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = True

w("=" * 78)
w("round24 —— I2C 驱动写路径确证（capstone 原生 reg_name）")
w("=" * 78)
w("")

SEG_LO, SEG_HI = 0x1D300, 0x1DA80
insns = list(md.disasm(D[SEG_LO:SEG_HI], BASE + SEG_LO))
w("反汇编 0x%05X-0x%05X -> %d 条指令, udf %d 条" %
  (SEG_LO, SEG_HI, len(insns), sum(1 for i in insns if i.mnemonic == "udf")))
w("")

I2C_REGS = {0x00: "CR1", 0x04: "CR2", 0x08: "OAR1", 0x0C: "OAR2",
            0x10: "DR", 0x14: "SR1", 0x18: "SR2", 0x1C: "CCR",
            0x20: "TRISE", 0x24: "FLTR"}

# 建 寄存器->常量 的流式表（线性扫描，遇到 call/branch 则清空对应项保守处理）
const = {}   # reg_name -> int

def const_propagate(ins):
    global const
    if ins.mnemonic in ("mov", "movs", "mov.w") and len(ins.operands) == 2 and \
       ins.operands[0].type == ARM_OP_REG:
        rd = ins.reg_name(ins.operands[0].reg)
        if ins.operands[1].type == ARM_OP_IMM:
            const[rd] = ins.operands[1].imm
        elif ins.operands[1].type == ARM_OP_REG:
            rs = ins.reg_name(ins.operands[1].reg)
            if rs in const:
                const[rd] = const[rs]
            else:
                const.pop(rd, None)
        else:
            const.pop(rd, None)
    elif ins.mnemonic == "movw" and len(ins.operands) == 2 and \
         ins.operands[1].type == ARM_OP_IMM and ins.operands[0].type == ARM_OP_REG:
        rd = ins.reg_name(ins.operands[0].reg)
        const[rd] = ins.operands[1].imm & 0xFFFF
    elif ins.mnemonic == "movt" and len(ins.operands) == 2 and \
         ins.operands[1].type == ARM_OP_IMM and ins.operands[0].type == ARM_OP_REG:
        rd = ins.reg_name(ins.operands[0].reg)
        const[rd] = (const.get(rd, 0) & 0xFFFF) | ((ins.operands[1].imm & 0xFFFF) << 16)
    elif ins.mnemonic in ("orr", "add", "sub", "and", "bic", "eor") and len(ins.operands) == 2:
        if ins.operands[0].type == ARM_OP_REG and ins.operands[1].type == ARM_OP_IMM:
            rd = ins.reg_name(ins.operands[0].reg)
            if rd in const:
                a, b = const[rd], ins.operands[1].imm
                if ins.mnemonic == "orr": const[rd] = a | b
                elif ins.mnemonic == "add": const[rd] = (a + b) & 0xFFFFFFFF
                elif ins.mnemonic == "sub": const[rd] = (a - b) & 0xFFFFFFFF
                elif ins.mnemonic == "and": const[rd] = a & b
                elif ins.mnemonic == "bic": const[rd] = a & ~b
                elif ins.mnemonic == "eor": const[rd] = a ^ b
            else:
                const.pop(rd, None)
        elif ins.operands[0].type == ARM_OP_REG:
            rd = ins.reg_name(ins.operands[0].reg)
            const.pop(rd, None)
    elif ins.mnemonic in ("lsl", "lsr", "asr", "ror", "asrs", "lsls", "lsrs") and len(ins.operands) == 2:
        if ins.operands[0].type == ARM_OP_REG and ins.operands[1].type == ARM_OP_IMM:
            rd = ins.reg_name(ins.operands[0].reg)
            if rd in const:
                sh = ins.operands[1].imm
                a = const[rd]
                if "lsr" in ins.mnemonic: const[rd] = a >> sh
                elif "asr" in ins.mnemonic: const[rd] = a >> sh
                elif "ror" in ins.mnemonic: const[rd] = ((a >> sh) | (a << (32 - sh))) & 0xFFFFFFFF
                else: const[rd] = (a << sh) & 0xFFFFFFFF
            else:
                const.pop(rd, None)
    elif ins.mnemonic.startswith(("ldr", "ldrb", "ldrh")):
        if ins.operands and ins.operands[0].type == ARM_OP_REG:
            rd = ins.reg_name(ins.operands[0].reg)
            # ldr rd, [pc, #imm] -> 字面量池，可解析
            if len(ins.operands) == 2 and ins.operands[1].type == ARM_OP_MEM and \
               ins.operands[1].mem.base != 0 and ins.reg_name(ins.operands[1].mem.base) == "pc":
                lit = ins.address + 4 + ins.operands[1].mem.disp
                if ins.address % 4 == 0:
                    lit -= 2  # Thumb pc 对齐
                fo = lit - BASE
                if 0 <= fo <= len(D) - 4:
                    v = int.from_bytes(D[fo:fo+4], "little")
                    const[rd] = v
                    w("      [literal pool] 0x%05X ldr %s, [pc,#%d] -> 0x%08X" %
                      (ins.address - BASE, rd, ins.operands[1].mem.disp, v))
                    return
            const.pop(rd, None)

# 先扫一遍，打印所有 I2C 寄存器的写 + 数据源数值
w("-" * 78)
w("### I2C 寄存器写序列（含定值传播）")
w("-" * 78)
const.clear()
for ins in insns:
    opstr = "%s %s" % (ins.mnemonic, ins.op_str)
    # 判断是否写 I2C 寄存器
    if ins.mnemonic.startswith(("str", "strb", "strh")):
        if ins.operands:
            last = ins.operands[-1]
            if last.type == ARM_OP_MEM and last.mem.disp in I2C_REGS:
                regname = I2C_REGS[last.mem.disp]
                basereg = ins.reg_name(last.mem.base)
                # 数据源
                src = ""
                if ins.operands[0].type == ARM_OP_IMM:
                    src = "imm 0x%X" % ins.operands[0].imm
                elif ins.operands[0].type == ARM_OP_REG:
                    rs = ins.reg_name(ins.operands[0].reg)
                    v = const.get(rs)
                    src = "%s=%s" % (rs, ("0x%X" % v) if v is not None else "?")
                w("  0x%05X  %-22s [%s,#0x%02X]=%-5s  <= %s" %
                  (ins.address - BASE, opstr, basereg, last.mem.disp, regname, src))
    # 顺带记录所有出现在 I2C 段的立即数（从地址候选）
    const_propagate(ins)

w("")
# ---- 关键统计 ----
w("-" * 78)
w("### 判定：DR 写入的数据源是否出现从地址")
w("-" * 78)
# 重扫，专挑 DR(0x10)
const.clear()
dr_writes = []
for ins in insns:
    if ins.mnemonic.startswith(("str", "strb", "strh")) and ins.operands:
        last = ins.operands[-1]
        if last.type == ARM_OP_MEM and last.mem.disp == 0x10:
            src = None
            if ins.operands[0].type == ARM_OP_IMM:
                src = ins.operands[0].imm
            elif ins.operands[0].type == ARM_OP_REG:
                src = const.get(ins.reg_name(ins.operands[0].reg))
            dr_writes.append((ins.address - BASE, src, ins.op_str))
    const_propagate(ins)
w("  写入 DR 的指令数: %d" % len(dr_writes))
for off, src, ops in dr_writes:
    w("      0x%05X  %-24s  src=%s" % (off, ops, ("0x%X" % src) if src is not None else "?(运行时)"))
w("")

# ---- 从地址候选扫描（整个 I2C 段的所有立即数） ----
w("-" * 78)
w("### I2C 段内全部立即数（从地址候选库）")
w("-" * 78)
imms = {}
for ins in insns:
    for opd in ins.operands:
        if opd.type == ARM_OP_IMM:
            v = opd.imm
            if 0 <= v <= 0xFF:
                imms.setdefault(v, []).append(ins.address - BASE)
cands = {0x5A: "7bit 0x2D", 0x5B: "7bit 0x2D R", 0xB4: "8bit (0x5A<<1)",
         0xB5: "8bit R", 0xC8: "7bit 0x64", 0x64: "7bit 0x32",
         0x70: "7bit 0x38", 0x90: "7bit 0x48", 0x20: "7bit 0x10",
         0x40: "7bit 0x20", 0x48: "7bit 0x24", 0x50: "7bit 0x28"}
w("  与触觉芯片常见地址相关的立即数出现情况:")
for c, tag in sorted(cands.items()):
    if c in imms:
        sites = imms[c]
        w("     0x%02X (%s): %d 处  @ %s" % (c, tag, len(sites), ", ".join("0x%X" % s for s in sites[:8])))
    else:
        w("     0x%02X (%s): 0 处" % (c, tag))
w("")
w("  段内全部 0x00-0xFF 立即数频次 Top25:")
for v, sites in sorted(imms.items(), key=lambda kv: -len(kv[1]))[:25]:
    w("     0x%02X : %d" % (v, len(sites)))
w("")
w("=" * 78)
w("round24 结束")
w("=" * 78)
open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("\n[saved] " + OUT)
