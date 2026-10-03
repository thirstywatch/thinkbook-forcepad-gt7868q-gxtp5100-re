# -*- coding: utf-8 -*-
"""(a) who reads the 'armed' flag (ctx_base 0x2000495E + 0x1690 = 0x20005FEE)
   (b) list the dispatcher's class comparisons, incl. the 0x80 class."""
import re
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

FW = r"<WORKSPACE>"
BASE = 0x08000000
D = open(FW, "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def sweep(lo, hi):
    out, o = [], 0
    while o < len(D):
        got = False
        for i in md.disasm(D[o:], BASE + o):
            if lo <= i.address < hi:
                out.append(i)
            got = True
            o = i.address - BASE + i.size
        if not got:
            o += 2
    return out


ALL = sweep(0, BASE + len(D))

print("== (a) sites that materialise ctx base 0x2000495E ==")
ctx = [i for i in ALL if i.mnemonic == "movw" and i.op_str.endswith("#0x495e")]
print("  count:", len(ctx))
print("  addrs:", ", ".join("%06X" % i.address for i in ctx[:20]))
print()

print("== (a2) every site using immediate #0x1690 (offset of the flag) ==")
s1690 = [i for i in ALL if "0x1690" in i.op_str]
print("  count:", len(s1690))
for i in s1690[:10]:
    print("  --- %06X ---" % i.address)
    for j in ALL:
        if i.address - 16 <= j.address <= i.address + 8:
            mark = " <=" if j.address == i.address else ""
            print("      %06X  %-8s %s%s" % (j.address, j.mnemonic, j.op_str, mark))
print()

print("== (b) dispatcher class comparisons around 0x080091C0 ==")
for i in ALL:
    if 0x08009100 <= i.address <= 0x08009360:
        if i.mnemonic in ("cmp", "cmp.w") and re.search(r"#0x(80|a0|a1|81|82|ff|20)\b", i.op_str):
            print("  %06X  %-8s %s" % (i.address, i.mnemonic, i.op_str))
print()

print("== (b2) full dispatcher head 0x080091C0..0x08009260 ==")
for i in ALL:
    if 0x080091C0 <= i.address < 0x08009260:
        print("  %06X  %-10s %s" % (i.address, i.mnemonic, i.op_str))
