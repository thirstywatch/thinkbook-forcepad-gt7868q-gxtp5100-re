# -*- coding: utf-8 -*-
"""List every OperationRegion (with space name) and every Field list in the dumped ACPI tables."""
import os, re, glob, struct

DIR = r"<WORKSPACE>"
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

def rd_int(d, i):
    if i >= len(d):
        return None, 0
    op = d[i]
    if op == 0x00:
        return 0, 1
    if op == 0x01:
        return 1, 1
    if op == 0x0A:
        return d[i + 1], 2
    if op == 0x0B:
        return struct.unpack_from("<H", d, i + 1)[0], 3
    if op == 0x0C:
        return struct.unpack_from("<I", d, i + 1)[0], 5
    if op == 0x0E:
        return struct.unpack_from("<Q", d, i + 1)[0], 9
    return None, 0

files = sorted(glob.glob(os.path.join(DIR, "*.bin")))
blobs = {os.path.basename(f): open(f, "rb").read() for f in files}

SPACE = {0: "SystemMemory", 1: "SystemIO", 2: "PCI_Config", 3: "EmbeddedControl",
         4: "SMBus", 5: "SystemCMOS", 6: "PCIBarTarget", 7: "IPMI", 8: "GeneralPurposeIO",
         9: "GenericSerialBus", 10: "PCC"}

print("== every OperationRegion (5B 80) ==")
region_space = {}
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
        sp = d[j + 6]
        label = SPACE.get(sp)
        if sp == 0:
            label = d[j + 7:j + 23].decode("ascii", "replace").strip("\x00")
        region_space[nm.decode()] = (fn, label)
        print("  %-42s name=%-5s space=0x%02X (%s)" % (fn, nm.decode(), sp, label))
print()

print("== every Field (5B 81) -> parsed EC/region byte maps ==")
def parse_field_list(d, i, end):
    out, bitpos = [], 0
    while i < end:
        if d[i] == 0x5B:
            break
        nm = d[i:i + 4]
        if not is_nameseg(nm):
            break
        val, n = pkg_len(d, i + 4)
        if val is None:
            break
        i += 4 + n
        if val == 0:
            v, k = rd_int(d, i)
            if v is None:
                break
            i += k
            bitpos = v * 8
            out.append((nm.decode(), v, 0, 0, "offset"))
            continue
        out.append((nm.decode(), bitpos // 8, bitpos % 8, val, "field"))
        bitpos += val
    return out, i

for fn, d in blobs.items():
    i = 0
    while True:
        j = d.find(b"\x5b\x81", i)
        if j < 0:
            break
        i = j + 2
        fname, rname = d[j + 2:j + 6], d[j + 6:j + 10]
        if not (is_nameseg(fname) and is_nameseg(rname)):
            continue
        flags = d[j + 10]
        fields, _ = parse_field_list(d, j + 11, min(len(d), j + 11 + 4000))
        rinfo = region_space.get(rname.decode(), ("?", "?"))
        if not fields:
            continue
        print("-- %s  field=%-5s region=%-5s (%s)  flags=0x%02X  %d entries"
              % (fn, fname.decode(), rname.decode(), rinfo[1], flags, len(fields)))
        for name, bo, bb, w, kind in fields:
            if kind == "offset":
                print("      ----  Offset -> 0x%02X (%d)" % (bo, bo))
            else:
                print("      0x%02X.%d  %-5s  %d bit" % (bo, bb, name, w))
        print()
