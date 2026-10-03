"""共享：从原始 bin 取 TF100A 明文段，capstone(thumb) 递归下降反汇编。
只读已有文件，不修改。
"""
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_INS_B, ARM_INS_BL, ARM_INS_BLX, ARM_INS_CBZ, ARM_INS_CBNZ
from capstone.arm import ARM_INS_TBB, ARM_INS_TBH

ROOT = r"<WORKSPACE>"
BIN = os.path.join(ROOT, "touchpad_GT7868Q_fw.bin")
ASM = os.path.join(ROOT, "touchpad_TF100A_thumb.asm.txt")

BASE_ADDR = 0x08005000
FILE_OFF = 0x19ABC
SEG_LO = 0x08005000
SEG_HI = 0x08012C9F          # inclusive
VEC_LO = 0x08005000
VEC_HI = 0x0800517F

def seg():
    d = open(BIN, "rb").read()
    off = FILE_OFF
    n = SEG_HI - SEG_LO + 1
    return d[off:off + n]

def md():
    m = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    m.detail = True
    return m

def insn_at(m, data, addr):
    """定点解码：只取一条指令。"""
    o = addr - SEG_LO
    if o < 0 or o >= len(data):
        return None
    for i in m.disasm(data[o:o + 4], addr):
        return i
    return None

def recursive_descent(data, entries, md_=None):
    """从 entries 出发递归下降。返回 {addr: insn}。遇到 bl/b 目标继续跟。"""
    m = md_ or md()
    code = {}
    work = list(entries)
    while work:
        pc = work.pop()
        while True:
            if pc in code:
                break
            o = pc - SEG_LO
            if o < 0 or o + 1 >= len(data) or pc > SEG_HI - 1:
                break
            i = insn_at(m, data, pc)
            if i is None:
                break
            code[pc] = i
            nxt = pc + i.size
            mn = i.mnemonic
            if mn in ("b", "b.w"):
                # 条件跳转也继续顺序走
                if i.cc != 0:  # ARM_CC_AL == 0
                    t = i.operands[0]
                    if t.type == 2:  # imm
                        work.append(t.imm)
                    work.append(nxt)
                    break
                t = i.operands[0]
                if t.type == 2:
                    pc = t.imm
                    continue
                break
            if mn in ("bl", "blx"):
                t = i.operands[0]
                if t.type == 2:
                    work.append(t.imm)
                # 顺序继续
            if mn in ("cbz", "cbnz"):
                t = i.operands[1]
                if t.type == 2:
                    work.append(t.imm)
            if mn in ("tbb", "tbh"):
                break  # 跳转表：由调用方另行处理
            if mn in ("pop", "bx", "ldr", "b.w") and "pc" in i.op_str:
                pass
            if mn == "bx" or mn == "pop" or mn in ("udf", "svc", "bkpt"):
                break
            if mn.startswith("ldm") and "pc" in i.op_str:
                break
            if mn == "b" and i.cc == 0:
                break
            pc = nxt
    return code

def vec_entries(data):
    """向量表里所有看起来像 Thumb 代码指针的条目。"""
    e = []
    for i in range(0, 0x180, 4):
        w = int.from_bytes(data[i:i + 4], "little")
        if 0x08005000 <= w <= SEG_HI and w & 1:
            e.append(w & ~1)
    return e
