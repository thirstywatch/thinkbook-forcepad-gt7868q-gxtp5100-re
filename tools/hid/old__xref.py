"""verify-B/xref.py — 列出所有引用了地址 A 或落到 [lo,hi] 的指令（含 ldr 池）"""
import struct, sys, re
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM
BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO
def rd32(a):
    o = off(a); return struct.unpack_from("<I", data, o)[0] if 0 <= o <= len(data)-4 else None
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
ALL = []
a = A_LO
while a <= A_HI:
    ok=False
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; ok=True; break
    if not ok: a += 2

lo, hi = int(sys.argv[1],16), int(sys.argv[2],16)
print("搜索引用落于 [%08X, %08X] 的指令" % (lo,hi))
for ins in ALL:
    for k, op in enumerate(ins.operands):
        v = None
        if op.type == ARM_OP_IMM: v = op.imm & 0xFFFFFFFF
        elif op.type == ARM_OP_MEM and op.mem.base and ins.reg_name(op.mem.base) == "pc":
            v = rd32(((ins.address+4)&~3)+op.mem.disp)
        if v is not None and lo <= v <= hi:
            print("  %08X  %-9s %-30s  ref=0x%08X" % (ins.address, ins.mnemonic, ins.op_str, v))
