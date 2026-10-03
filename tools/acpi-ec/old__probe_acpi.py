# -*- coding: utf-8 -*-
"""Targeted probe: does an EmbeddedControl region exist? What does _LID / VPCR / VPCW look like?"""
import os, re, glob, struct, collections

DIR = r"<WORKSPACE>"
files = sorted(glob.glob(os.path.join(DIR, "*.bin")))
blobs = {os.path.basename(f): open(f, "rb").read() for f in files}

print("== region space-name literals present ==")
for lit in (b"EmbeddedControl", b"SystemIO", b"SystemMemory", b"PCI_Config", b"SMBus",
            b"GeneralPurposeIO", b"GenericSerialBus", b"SystemCMOS", b"IPMI", b"PCC"):
    hit = [f for f, d in blobs.items() if lit in d]
    print("  %-18s %d table(s) %s" % (lit.decode(), len(hit), ", ".join(hit[:3]) + (" ..." if len(hit) > 3 else "")))
print()

print("== OperationRegion counts by space byte ==")
cnt = collections.Counter()
sp3 = []
for fn, d in blobs.items():
    i = 0
    while True:
        j = d.find(b"\x5b\x80", i)
        if j < 0:
            break
        i = j + 2
        nm = d[j + 2:j + 6]
        if not all(c in b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in nm):
            continue
        sp = d[j + 6]
        cnt[sp] += 1
        if sp == 3:
            sp3.append((fn, nm.decode(), j))
for k in sorted(cnt):
    print("  space=0x%02X : %d" % (k, cnt[k]))
print()
print("  >>> EmbeddedControl (0x03) regions:", sp3 if sp3 else "NONE")
print()

print("== name presence (4-char NameSegs) ==")
def namesegs(d):
    s = set()
    for m in re.finditer(rb"[A-Z_][A-Z0-9_]{3}", d):
        s.add(m.group(0).decode())
    return s
per = {f: namesegs(d) for f, d in blobs.items()}
for key in ("EC0_", "EC__", "VPC0", "VPCR", "VPCW", "LID0", "_LID", "HALS", "GBMD", "DYTC",
            "VPC1", "ECDT", "ERAM", "ECRM", "HECI", "ISHM", "SEN1", "TMP1"):
    hit = [f.split("_")[0] for f, s in per.items() if key in s]
    print("  %-6s %d: %s" % (key, len(hit), ", ".join(hit[:8])))
print()

def dump_around(d, off, before=64, after=192):
    a = max(0, off - before)
    b = min(len(d), off + after)
    return d[a:b].hex(" ")

print("== _LID occurrences ==")
for fn, d in blobs.items():
    for m in re.finditer(rb"_LID", d):
        print("  [%s] @0x%06X" % (fn, m.start()))
        print("     ", dump_around(d, m.start()))
print()

print("== VPCR / VPCW occurrences ==")
for key in (b"VPCR", b"VPCW"):
    for fn, d in blobs.items():
        for m in re.finditer(key, d):
            print("  [%s] %s @0x%06X" % (fn, key.decode(), m.start()))
            print("     ", dump_around(d, m.start(), 48, 160))
print()

print("== _Q15 / _Q04 method bodies ==")
for key in (b"_Q15", b"_Q04"):
    for fn, d in blobs.items():
        for m in re.finditer(key, d):
            print("  [%s] %s @0x%06X" % (fn, key.decode(), m.start()))
            print("     ", dump_around(d, m.start(), 16, 160))
