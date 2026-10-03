# -*- coding: utf-8 -*-
import os, glob
DIR = r"<WORKSPACE>"
files = sorted(glob.glob(os.path.join(DIR, "*.bin")))
NAME_OK = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
def is_nameseg(b):
    if len(b) != 4 or not (b[0:1].isalpha() or b[0:1] == b"_"): return False
    return all(c in NAME_OK for c in b)
def pkg_len(d, i):
    if i >= len(d): return None, 0
    lead = d[i]; n = lead >> 6
    if n == 0: return lead & 0x3F, 1
    v = lead & 0x0F
    for k in range(1, n+1):
        if i+k >= len(d): return None, 0
        v |= d[i+k] << (8*k)
    return v, n+1
def parse(d, i, end):
    out, bitpos = [], 0
    while i < end:
        b = d[i]
        if b == 0x00:
            v, n = pkg_len(d, i+1)
            if v is None: break
            i += 1+n; bitpos += v
        elif b == 0x01: i += 3
        elif b == 0x02:
            i += 1
            if i < len(d) and d[i] == 0x11:
                v, n = pkg_len(d, i+1); i += 1+n
            else: i += 4
        elif b == 0x03: i += 4
        else:
            nm = d[i:i+4]
            if not is_nameseg(nm): break
            v, n = pkg_len(d, i+4)
            if v is None: break
            i += 4+n
            out.append((nm.decode(), bitpos//8, bitpos % 8, v))
            bitpos += v
    return out
hits = 0
for fn, path in [(os.path.basename(p), p) for p in files]:
    d = open(path, "rb").read()
    i = 0
    while True:
        j = d.find(b"\x5b\x81", i)
        if j < 0: break
        i = j+2
        v, n = pkg_len(d, j+2)
        if v is None: continue
        k = j+2+n
        rn = d[k:k+4]
        if not is_nameseg(rn): continue
        flags = d[k+4]
        flds = parse(d, k+5, min(j+2+n+v, len(d)))
        if not flds: continue
        hits += 1
        print("%-40s Field(%-5s) flags=0x%02X  %d entries" % (fn, rn.decode(), flags, len(flds)))
        if any(f[0] in ("LIDF","LIDS","PLID","ECRD","ECOK","S3ST","S4ST","S5ST","OSTY","TOFE","ANGL","HING","LANG") for f in flds):
            for f in flds:
                print("       0x%03X.%d %-5s %d bit" % (f[1], f[2], f[0], f[3]))
print("total Field ops parsed:", hits)
