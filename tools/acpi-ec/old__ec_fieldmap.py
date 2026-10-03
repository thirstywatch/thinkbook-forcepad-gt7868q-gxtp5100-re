# -*- coding: utf-8 -*-
"""Correct AML Field (5B 81) parser -> EC RAM byte map for EmbeddedControl regions."""
import os, glob, struct

DIR = r"<WORKSPACE>"
files = sorted(glob.glob(os.path.join(DIR, "*.bin")))
blobs = {os.path.basename(f): open(f, "rb").read() for f in files}
NAME_OK = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

def is_nameseg(b):
    if len(b) != 4 or not (b[0:1].isalpha() or b[0:1] == b"_"):
        return False
    return all(c in NAME_OK for c in b)

def pkg_len(d, i):
    if i >= len(d):
        return None, 0
    lead = d[i]
    n = lead >> 6
    if n == 0:
        return lead & 0x3F, 1
    v = lead & 0x0F
    for k in range(1, n + 1):
        if i + k >= len(d):
            return None, 0
        v |= d[i + k] << (8 * k)
    return v, n + 1

# 1) collect EmbeddedControl regions
ec_regions = {}
for fn, d in blobs.items():
    i = 0
    while True:
        j = d.find(b"\x5b\x80", i)
        if j < 0:
            break
        i = j + 2
        nm = d[j + 2:j + 6]
        if not is_nameseg(nm):
            continue
        if d[j + 6] == 0x03:
            ec_regions[nm.decode()] = fn

print("== EmbeddedControl regions ==")
for k, v in ec_regions.items():
    print("  %-5s in %s" % (k, v))
print()

# 2) parse every Field (5B 81) whose region is an EmbeddedControl region
def parse_fieldlist(d, i, end):
    out, bitpos = [], 0
    while i < end:
        b = d[i]
        if b == 0x00:                                   # ReservedField: pkg = bits to skip
            v, n = pkg_len(d, i + 1)
            if v is None:
                break
            i += 1 + n
            out.append(("----", bitpos // 8, bitpos % 8, v, "reserved"))
            bitpos += v
        elif b == 0x01:                                 # AccessField
            i += 3
        elif b == 0x02:                                 # ConnectField
            i += 1
            if i < len(d) and d[i] == 0x11:             # BufferData
                v, n = pkg_len(d, i + 1)
                i += 1 + n
            else:
                i += 4
        elif b == 0x03:                                 # ExtendedAccessField
            i += 4
        else:
            nm = d[i:i + 4]
            if not is_nameseg(nm):
                break
            v, n = pkg_len(d, i + 4)
            if v is None:
                break
            i += 4 + n
            out.append((nm.decode(), bitpos // 8, bitpos % 8, v, "field"))
            bitpos += v
    return out, i

found = False
for fn, d in blobs.items():
    i = 0
    while True:
        j = d.find(b"\x5b\x81", i)
        if j < 0:
            break
        i = j + 2
        v, n = pkg_len(d, j + 2)
        if v is None:
            continue
        k = j + 2 + n
        rname = d[k:k + 4]
        if not is_nameseg(rname):
            continue
        rn = rname.decode()
        if rn not in ec_regions:
            continue
        flags = d[k + 4]
        plen = j + 2 + n + v          # absolute end of the Field package
        fields, _ = parse_fieldlist(d, k + 5, min(plen, len(d)))
        if not fields:
            continue
        found = True
        print("== %s : Field(%s)  flags=0x%02X  %d entries ==" % (fn, rn, flags, len(fields)))
        for name, bo, bb, w, kind in fields:
            if kind == "reserved":
                print("    0x%03X.%d  <reserved>  %d bit" % (bo, bb, w))
            else:
                print("    0x%03X.%d  %-5s  %d bit" % (bo, bb, name, w))
        print()
if not found:
    print("(no Field bound to an EmbeddedControl region)")
