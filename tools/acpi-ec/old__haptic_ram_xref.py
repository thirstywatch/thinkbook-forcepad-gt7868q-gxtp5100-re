# -*- coding: utf-8 -*-
"""Who materialises / touches the haptic-related RAM addresses and the LRA callback?
Scans Thumb-2 movw/movt pairs (and literal pools) to resolve 32-bit constants."""
import re, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

FW = r"<WORKSPACE>"
BASE = 0x08000000
D = open(FW, "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = False


def sweep():
    out, o = [], 0
    while o < len(D):
        got = False
        for i in md.disasm(D[o:], BASE + o):
            out.append(i); got = True
            o = i.address - BASE + i.size
        if not got:
            o += 2
    return out


INS = sweep()
print("insns:", len(INS), "of", len(D), "bytes\n")

# ---- collect movw/movt -> 32-bit constants ----
movw = {}      # addr -> (reg, imm16)
movt = {}
for i in INS:
    m = re.match(r"(\w+),\s*#(0x[0-9a-f]+|\d+)$", i.op_str)
    if not m:
        continue
    reg, imm = m.group(1), int(m.group(2), 0)
    if i.mnemonic == "movw" and reg.startswith("r") and not reg.startswith("r1"):
        movw[i.address] = (reg, imm & 0xFFFF)
    elif i.mnemonic == "movt" and reg.startswith("r") and not reg.startswith("r1"):
        movt[i.address] = (reg, imm & 0xFFFF)

consts = []    # (addr_of_movw, reg, value)
for a, (reg, lo) in sorted(movw.items()):
    for b in range(a + 2, a + 12, 2):
        if b in movt and movt[b][0] == reg:
            consts.append((a, reg, (movt[b][1] << 16) | lo, b))
            break

print("movw/movt pairs resolved:", len(consts))

# ---- literal pool scan: any 4-byte word equal to a target address ----
def literal_refs(val):
    hits = []
    b = val.to_bytes(4, "little")
    o = D.find(b)
    while o >= 0:
        hits.append(BASE + o)
        o = D.find(b, o + 1)
    return hits

TARGETS = {
    "LRA ctx base 0x200040D0":      0x200040D0,
    "LRA ctx +0x14 (cb slot)":      0x200040E4,
    "LRA ctx +0x10 (counter)":      0x200040E0,
    "wave buffer 0x200040E8":       0x200040E8,
    "44B struct 0x2000426C":        0x2000426C,
    "armed flag 0x20005FEE":        0x20005FEE,
    "wave cb ptr 0x0800D6F4":       0x0800D6F4,
    "play wrapper 0x08008628":      0x08008628,
    "indirect callr 0x08008858":    0x08008858,
    "TIM3 cfg 0x08009750":          0x08009750,
    "PWM cfg 0x08008704":           0x08008704,
    "wave buf wr 0x080088C0":       0x080088C0,
    "clear/arm 0x080086B4":         0x080086B4,
    "TIM3 ISR 0x0800D628":          0x0800D628,
}

print("\n== who materialises each target address (movw/movt) ==")
for name, val in TARGETS.items():
    hits = [(a, reg) for (a, reg, v, _) in consts if v == val]
    lits = literal_refs(val)
    print("  %-30s mov/movt=%-3d %s" % (name, len(hits),
          ", ".join("0x%06X(%s)" % (a, r) for a, r in hits[:6])))
    if lits:
        print("  %-30s literal=%d %s" % ("", len(lits), ", ".join("0x%06X" % x for x in lits[:6])))
print()

# ---- for the armed flag and ctx, show the very next instructions (read or write?) ----
NEAR = {}
for addr, insn in ((i.address, i) for i in INS):
    NEAR[addr] = insn

def show_around(a, n=6):
    out = []
    for i in INS:
        if a <= i.address <= a + n * 4:
            out.append("      %06X  %-8s %s" % (i.address, i.mnemonic, i.op_str))
    return out

for name in ("armed flag 0x20005FEE", "LRA ctx +0x14 (cb slot)", "wave buffer 0x200040E8",
             "44B struct 0x2000426C", "wave cb ptr 0x0800D6F4"):
    val = TARGETS[name]
    print("== %s ==" % name)
    hits = [a for (a, reg, v, _) in consts if v == val]
    if not hits:
        print("      (no movw/movt site)")
    for a in hits[:4]:
        for line in show_around(a):
            print(line)
        print("      ---")
    print()
