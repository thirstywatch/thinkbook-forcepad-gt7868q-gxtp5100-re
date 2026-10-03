# -*- coding: utf-8 -*-
"""
round23_i2c_target.py —— 定位 I2C 写路径的目标从地址
背景：审计报告 U1/L5 遗留最高优先级问题 —— 「0x5A/0x5B 是否为 I2C 从地址」。
若为真 ⇒ 触觉芯片（AW86927 类）走独立 IC，与「滑动震动」目标直接相关。
方法：反汇编 I2C 相关函数（审计给出的 6 个 I2C1 引用点所在函数），
      把每条 str/strb 写入 I2C1->DR(0x40005410) 前的「数据来源」回溯出来：
      - 立即数来源 ⇒ 直接给出从地址/数据常量
      - 寄存器来源 ⇒ 回溯该寄存器由哪条 movw/movt/ldr 赋值
输出: cfg_parsed/round23_i2c_target.txt
"""
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round23_i2c_target.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
L = []
def w(s=""):
    L.append(str(s)); print(s, flush=True)

D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = True

I2C1 = 0x40005400
DR   = 0x40005410
SR1  = 0x40005414
SR2  = 0x40005418
CR2  = 0x40005404
CCR  = 0x4000541C
OAR1 = 0x40005408
OAR2 = 0x4000540C

w("=" * 78)
w("round23 —— I2C1 目标从地址定位")
w("=" * 78)
w("I2C1 base 0x%08X  DR 0x%08X  SR1 0x%08X  CR2 0x%08X" % (I2C1, DR, SR1, CR2))
w("")

# ---- 1. 全局扫描：谁把 I2C1 基址装进寄存器 ----
w("-" * 78)
w("### 1. 全文件扫描：I2C1 基址 / DR 的装载点")
w("-" * 78)
# 滑动 MOVW/MOVT 配对，找 imm16 等于 I2C1 低16位(0x5400) 的组合
def find_movw_movt(target_lo):
    """返回所有把 target_lo|hi 装入同一寄存器的 (offset, imm32, rd) 候选"""
    res = []
    n = len(D)
    for o in range(0, n - 4, 2):
        hw1 = D[o] | (D[o+1] << 8)
        if (hw1 >> 11) != 0b11110:
            continue
        op = hw1 & 0x0FF0
        if op not in (0x240, 0x2C0):
            continue
        hw2 = D[o+2] | (D[o+3] << 8)
        imm16 = ((hw1 & 0xF) << 12) | (((hw1 >> 10) & 1) << 11) | (((hw2 >> 12) & 7) << 8) | (hw2 & 0xFF)
        if imm16 != target_lo:
            continue
        rd = (hw2 >> 8) & 0xF
        # 找同一 rd 的 MOVT
        for o2 in range(o + 2, min(o + 14, n - 4)):
            g1 = D[o2] | (D[o2+1] << 8)
            if (g1 >> 11) != 0b11110:
                continue
            if (g1 & 0x0FF0) != 0x2C0:
                continue
            g2 = D[o2+2] | (D[o2+3] << 8)
            if ((g2 >> 8) & 0xF) != rd:
                continue
            hi16 = ((g1 & 0xF) << 12) | (((g1 >> 10) & 1) << 11) | (((g2 >> 12) & 7) << 8) | (g2 & 0xFF)
            res.append((o, (hi16 << 16) | imm16, rd))
    return res

hits = {}
for lo in (0x5400, 0x5410, 0x5414, 0x5404):
    r = find_movw_movt(lo)
    hits[lo] = r
    w("  imm16=0x%04X 命中 %d 处:" % (lo, len(r)))
    for o, imm32, rd in r[:14]:
        tag = ""
        if imm32 == I2C1: tag = "  <== I2C1 base"
        elif imm32 == DR: tag = "  <== DR"
        elif imm32 == SR1: tag = "  <== SR1"
        elif imm32 == CR2: tag = "  <== CR2"
        w("      file 0x%05X  va 0x%08X  imm32=0x%08X  rd=r%d%s" % (o, BASE + o, imm32, rd, tag))
w("")

# ---- 2. 反汇编每个 I2C1 引用点所在函数，提取写序列 ----
w("-" * 78)
w("### 2. I2C1 引用点所在函数的写序列（DR 写入前的数据来源）")
w("-" * 78)
I2C_SITES = [0x1D40A, 0x1D436, 0x1D45E, 0x1D486, 0x1D4AE, 0x1D4F0, 0x1D51C, 0x1D554, 0x1D57C, 0x1D5A8, 0x1D614, 0x1D644, 0x241AC]

def find_func_start(off):
    """向前找最近的 PUSH{...,LR}，作为函数起点近似"""
    for o in range(off - 1, max(0, off - 0x800), -2):
        hw = D[o] | (D[o+1] << 8)
        # PUSH (T1) = 1011 010x xxxxxxxx with bit8 set (LR)
        if (hw & 0xFE00) == 0xB400 and (hw & 0x0100):
            return o
        # STMDB sp!, {...} = 2D E9 xx xx
        if hw == 0xE92D:
            return o
    return max(0, off - 0x100)

def disasm_func(start, maxlen=0x600):
    end = min(len(D), start + maxlen)
    insns = list(md.disasm(D[start:end], BASE + start))
    return insns

def trace_dr_writes(insns):
    """找 str/strb 到 [reg, #0x10] 或 [reg] 且 reg 指向 I2C1 的写，回溯数据源"""
    out = []
    # 先建 寄存器常量表（movw/movt/ldr =addr）
    for i, ins in enumerate(insns):
        if ins.mnemonic in ("str", "strb", "strh", "str.w", "strb.w"):
            if not ins.operands:
                continue
            # 目标操作数 = operands[-1]，基址可能 +偏移
            last = ins.operands[-1]
            off = 0
            if last.type == ARM_OP_MEM:
                off = last.mem.disp
                base_reg = last.mem.base
            else:
                continue
            # 判断是否 I2C 区（0x10=DR, 0x14=SR1, 0x00=CR1, 0x04=CR2, 0x08=OAR1, 0x0C=OAR2, 0x1C=CCR, 0x20=TRISE）
            if off not in (0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28):
                continue
            # 数据源
            src_desc = "?"
            if ins.operands[0].type == ARM_OP_IMM:
                src_desc = "imm 0x%X" % ins.operands[0].imm
            elif ins.operands[0].type == ARM_OP_REG:
                rn = ins.operands[0].reg
                # 向上回溯 12 条内的赋值
                val = None
                for j in range(i - 1, max(-1, i - 14), -1):
                    p = insns[j]
                    if p.mnemonic in ("movw", "mov", "movs") and p.operands and \
                       p.operands[0].type == ARM_OP_REG and p.operands[0].reg == rn and \
                       len(p.operands) > 1 and p.operands[1].type == ARM_OP_IMM:
                        val = p.operands[1].imm
                        src_desc = "%s r%d <- 0x%X @0x%X" % (p.mnemonic, rn, val, p.address - BASE)
                        break
                    if p.mnemonic == "movt" and p.operands and \
                       p.operands[0].type == ARM_OP_REG and p.operands[0].reg == rn:
                        if len(p.operands) > 1 and p.operands[1].type == ARM_OP_IMM:
                            src_desc = "movt r%d <- 0x%X (high) @0x%X" % (rn, p.operands[1].imm, p.address - BASE)
                        break
                    if p.mnemonic in ("ldrb", "ldrh", "ldr") and p.operands and \
                       p.operands[0].type == ARM_OP_REG and p.operands[0].reg == rn:
                        src_desc = "load into r%d @0x%X" % (rn, p.address - BASE)
                        break
                src_desc = "r%d " % rn + src_desc
            out.append((ins.address - BASE, ins.mnemonic, off, src_desc))
    return out

seen_funcs = set()
for site in I2C_SITES:
    fs = find_func_start(site)
    if fs in seen_funcs:
        continue
    seen_funcs.add(fs)
    insns = disasm_func(fs, 0x500)
    writes = trace_dr_writes(insns)
    w("  --- 函数 @0x%05X (含引用点 0x%05X), %d 条指令, 外围写 %d 处 ---" %
      (fs, site, len(insns), len(writes)))
    for off, mn, reg_off, desc in writes[:24]:
        w("      0x%05X  %-6s [base,#0x%02X]  <= %s" % (off, mn, reg_off, desc))
w("")

# ---- 3. 0x5A / 0xC8 / 0x20 作为立即数在 I2C 函数里的出现 ----
w("-" * 78)
w("### 3. 候选从地址立即数在 I2C 函数内的出现")
w("-" * 78)
CANDS = {0x5A: "7bit 0x2D (AW86927? )", 0x5B: "7bit 0x2D R", 0xB4: "8bit w 0x5A<<1",
         0xB5: "8bit r", 0xC8: "7bit 0x64", 0x20: "7bit 0x10", 0x64: "7bit 0x32",
         0x70: "7bit 0x38", 0x90: "7bit 0x48"}
for fs in sorted(seen_funcs):
    insns = disasm_func(fs, 0x500)
    found = []
    for ins in insns:
        for opd in ins.operands:
            if opd.type == ARM_OP_IMM:
                for c, tag in CANDS.items():
                    if opd.imm == c:
                        found.append((ins.address - BASE, ins.mnemonic, c, tag))
    if found:
        w("  函数 @0x%05X:" % fs)
        for off, mn, c, tag in found[:20]:
            w("      0x%05X  %-8s #0x%02X  (%s)" % (off, mn, c, tag))
w("")

w("=" * 78)
w("round23 结束")
w("=" * 78)
open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("\n[saved] " + OUT)
