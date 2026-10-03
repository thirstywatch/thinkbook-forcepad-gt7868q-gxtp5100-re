"""verify-B/ctx.py — 打印 I2C1 代码簇的完整反汇编（capstone 自然解码，权威）"""
import struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
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
AT = {i.address: i for i in ALL}

lo, hi = int(sys.argv[1],16), int(sys.argv[2],16)
for ins in ALL:
    if lo <= ins.address <= hi:
        print("%08X  %-9s %s" % (ins.address, ins.mnemonic, ins.op_str))
