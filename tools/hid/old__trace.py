"""verify-B/trace.py — 单点跟踪：在 0x08008A60 起逐条打印寄存器常量与命中情况"""
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM
BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
ALL = []
a = A_LO
while a <= A_HI:
    ok=False
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; ok=True; break
    if not ok: a += 2

regs = {}
LO, HI = 0x40005000, 0x400057FF
for i, ins in enumerate(ALL):
    if ins.address == 0x08008A5E:
        print(">>> 到达 0x08008A5E，之前 r0 =", hex(regs.get("r0", 0)))
    if 0x08008A5E <= ins.address <= 0x08008A70:
        print("%08X  %-8s %-24s   regs: %s" % (ins.address, ins.mnemonic, ins.op_str,
              {k: hex(v) for k, v in sorted(regs.items())}))
    if ins.mnemonic in ("mov","movs","movw","movt") and len(ins.operands)==2 \
       and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg); v = ins.operands[1].imm & 0xFFFFFFFF
        if ins.mnemonic=="movw": regs[r]=((regs.get(r,0)&0xFFFF0000)|(v&0xFFFF))&0xFFFFFFFF
        elif ins.mnemonic=="movt": regs[r]=((regs.get(r,0)&0xFFFF)|((v&0xFFFF)<<16))&0xFFFFFFFF
        else: regs[r]=v
    elif ins.mnemonic=="ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_MEM:
        m=ins.operands[1].mem
        if m.base and ins.reg_name(m.base)=="pc":
            o2=off(((ins.address+4)&~3)+m.disp)
            if 0 <= o2 <= len(data)-4:
                regs[ins.reg_name(ins.operands[0].reg)] = struct.unpack_from("<I",data,o2)[0]
    if ins.operands and ins.operands[0].type==ARM_OP_MEM and ins.operands[0].mem.base:
        m=ins.operands[0].mem; bn=ins.reg_name(m.base)
        if bn in regs:
            t=(regs[bn]+m.disp)&0xFFFFFFFF
            if LO<=t<=HI:
                print("    *** HIT %08X %s %s -> 0x%08X" % (ins.address, ins.mnemonic, ins.op_str, t))
    if ins.mnemonic in ("bl","blx"):
        regs={k:v for k,v in regs.items() if k=="r0"}
