#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the DSDT (and every other valid ACPI table) out of a firmware blob."""
import struct, sys, os

SIGS = ['DSDT', 'FACP', 'FACS', 'APIC', 'SSDT', 'TPM2', 'SRAT', 'SLIT', 'BERT',
        'HEST', 'DMAR', 'MCFG', 'HPET', 'ECDT', 'UEFI', 'BGRT', 'FPDT', 'WSMT',
        'LPIT', 'NHLT', 'PPTT', 'GTDT', 'IORT', 'SPCR', 'DBG2', 'MSDM', 'PHAT',
        'SSDT', 'TCPA', 'WAET', 'RGRT', 'RASF', 'PDTT', 'CEDT', 'AGDI']


def find_tables(d):
    out = []
    n = len(d)
    for sig in sorted(set(SIGS)):
        b = sig.encode()
        i = 0
        while True:
            i = d.find(b, i)
            if i < 0: break
            start = i; i += 1
            if start + 36 > n: continue
            ln = struct.unpack_from('<I', d, start+4)[0]
            if not (36 <= ln <= 0x400000) or start + ln > n: continue
            oem = d[start+10:start+16]
            if not all(c == 0 or (32 <= c <= 126) for c in oem): continue
            if (sum(d[start:start+ln]) & 0xFF) != 0: continue
            out.append((start, sig, ln))
    out.sort()
    # drop overlaps (keep longest container first)
    keep = []
    for o, s, l in out:
        if any(o >= k[0] and o + l <= k[0] + k[2] and (o, s, l) != k for k in out):
            continue
        keep.append((o, s, l))
    return keep


if __name__ == '__main__':
    src = sys.argv[1]
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    d = open(src, 'rb').read()
    ts = find_tables(d)
    print('%s: %d valid ACPI tables' % (src, len(ts)))
    for o, s, l in ts:
        tbl = d[o:o+l]
        print('  @0x%-9X %-5s len=%-8d rev=%d oem=%-8r otbl=%-8r' % (
            o, s, l, tbl[8], tbl[10:16], tbl[16:22]))
        if s == 'DSDT':
            fn = os.path.join(outdir, 'DSDT_X9-15.bin')
        else:
            fn = os.path.join(outdir, '%s_%08X.bin' % (s, o))
        open(fn, 'wb').write(tbl)
        print('      -> %s' % fn)
