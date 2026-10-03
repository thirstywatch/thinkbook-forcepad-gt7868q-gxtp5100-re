"""verify-B/halmap.py — 对 HAL 区每个函数，列出它通过哪个形参寄存器访问了哪些偏移
用于判断 0x08008B98→0x0800FA20 等调用中，I2C1 基址被写到哪些偏移。
"""
import struct, sys
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

def scan(lo, hi, params=("r0","r1","r2","r3")):
    """列出 [lo,hi] 内所有 [reg+disp] 访存，标出 reg 是否为形参"""
    print("函数 0x%08X..0x%08X  形参 %s" % (lo, hi, ",".join(params)))
    out = []
    for ins in ALL:
        if not (lo <= ins.address <= hi): continue
        m = None
        if ins.operands and ins.operands[0].type == ARM_OP_MEM: m = ins.operands[0].mem
        elif len(ins.operands)>=2 and ins.operands[1].type == ARM_OP_MEM: m = ins.operands[1].mem
        if m is not None and m.base and not m.index:
            bn = ins.reg_name(m.base)
            v = None
            for op in ins.operands:
                if op.type == ARM_OP_IMM: v = op.imm & 0xFFFFFFFF
            mark = "PARAM" if bn in params else "     "
            print("   %08X %-8s %-28s  base=%s disp=+0x%X %s %s" %
                  (ins.address, ins.mnemonic, ins.op_str, bn, m.disp, mark,
                   ("imm=0x%X" % v) if v is not None else ""))

for spec in sys.argv[1:]:
    lo, hi = [int(x,16) for x in spec.split(":")]
    scan(lo, hi)
    print()
