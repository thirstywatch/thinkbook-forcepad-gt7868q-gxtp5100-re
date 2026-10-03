# -*- coding: utf-8 -*-
"""(1) full A0/A1 subcommand -> handler table from the dispatcher
   (2) resolve the three 'armed' consumers: containing function, callers, and branch body"""
import re, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

FW = r"<WORKSPACE>"
BASE = 0x08000000
D = open(FW, "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def sweep():
    out, o = [], 0
    while o < len(D):
        g = False
        for i in md.disasm(D[o:], BASE + o):
            out.append(i); g = True
            o = i.address - BASE + i.size
        if not g:
            o += 2
    return out


INS = sweep()
BY = {i.address: i for i in INS}
bl_edges = collections.defaultdict(set)
rev = collections.defaultdict(set)
for i in INS:
    if i.mnemonic == "bl":
        try:
            t = int(i.op_str.lstrip("#"), 0)
        except ValueError:
            continue
        bl_edges[i.address & ~1].add(t & ~1)
        rev[t & ~1].add(i.address & ~1)


def fn_start(a):
    """nearest preceding push {..., lr} within 0x500 bytes"""
    for j in range(a, max(BASE, a - 0x500), -2):
        if j in BY:
            i = BY[j]
            if i.mnemonic == "push" and "lr" in i.op_str:
                return j
    return a


print("=" * 72)
print("(1) dispatcher subcommand tables")
print("=" * 72)
sub = []
for i in INS:
    if 0x08009214 <= i.address < 0x080093D2 and i.mnemonic.startswith("cmp"):
        m = re.search(r"#(0x[0-9a-f]+|\d+)", i.op_str)
        if not m:
            continue
        v = int(m.group(1), 0)
        if 0x100 <= v <= 0xFF00 and v % 0x100 == 0:
            tgt = None
            for k in range(i.address, i.address + 0x10, 2):
                if k in BY and BY[k].mnemonic.startswith("beq"):
                    tgt = BY[k].op_str.lstrip("#")
                    break
            sub.append((v >> 8, tgt, i.address))
for s, t, a in sub:
    print("   subcmd 0x%02X  (frame+2 == 0x%04X)  ->  %s   @%06X" % (s, s << 8, t, a))
print("   total: %d" % len(sub))
print()

print("=" * 72)
print("(2) the three 'armed' consumers")
print("=" * 72)
SITES = [0x800248C, 0x800479C, 0x800506E]
for site in SITES:
    f = fn_start(site)
    print("-" * 72)
    print("site %06X   containing function (probable) %06X" % (site, f))
    print("  is a BL target? %s   BL callers: %s" % (
        f in rev, ", ".join("%06X" % x for x in sorted(rev.get(f, ()))[:8]) or "<none>"))
    # walk callers up to depth 3
    seen, frontier, depth = {f}, {f}, 1
    while depth <= 3 and frontier:
        nxt = set()
        for x in frontier:
            nxt |= {c for c in rev.get(x, ()) if c not in seen}
        if not nxt:
            break
        print("  depth %d callers: %s" % (depth, ", ".join("%06X" % x for x in sorted(nxt)[:10])))
        for x in sorted(nxt)[:10]:
            if 0x080091C0 <= x < 0x08009440:
                print("       ^ %06X is inside the DISPATCHER / handler-stub region" % x)
        seen |= nxt
        frontier = nxt
        depth += 1
    print("  --- prologue + the cmp context ---")
    for j in range(f, f + 0x20, 2):
        if j in BY:
            print("      %06X  %-10s %s" % (j, BY[j].mnemonic, BY[j].op_str))
    print("  --- the armed branch body (site .. +0x50) ---")
    for j in range(site, site + 0x50, 2):
        if j in BY:
            mk = " <==" if j == site else ""
            print("      %06X  %-10s %s%s" % (j, BY[j].mnemonic, BY[j].op_str, mk))
    print()
