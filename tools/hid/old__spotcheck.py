import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
BIN = "touchpad_GT7868Q_fw.bin"
REGION_OFF, REGION_ADDR = 0x19ABC, 0x08005000
data = open(BIN, "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.detail = True
for a in (0x08008B10, 0x08008B14, 0x08008B18, 0x08008A44, 0x08008A48, 0x08008A4C):
    off = a - REGION_ADDR + REGION_OFF
    got = list(md.disasm(data[off:off + 4], a, count=1))
    if not got:
        print("%08X  <不可解码>" % a)
        continue
    ins = got[0]
    tgt = ""
    if ins.operands and ins.operands[0].type == 2:
        tgt = "  -> 0x%08X" % ins.operands[0].imm
    print("%08X  %-10s %-24s size=%d%s" % (a, ins.mnemonic, ins.op_str, ins.size, tgt))
