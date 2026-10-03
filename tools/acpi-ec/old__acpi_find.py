#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find and validate ACPI tables inside a raw blob / firmware image."""
import struct, sys, os

SIGS = [b'DSDT', b'FACP', b'FACS', b'APIC', b'SSDT', b'TPM2', b'SRAT', b'SLIT',
        b'BERT', b'HEST', b'DMAR', b'MCFG', b'HPET', b'ECDT', b'UEFI', b'BGRT',
        b'FPDT', b'WSMT', b'LPIT', b'NHLT', b'PPTT', b'GTDT', b'IORT', b'SPCR',
        b'DBG2', b'MSDM', b'TPM2', b'WSMT', b'PHAT', b'SSDT']


def tables(d):
    out = []
    n = len(d)
    for sig in set(SIGS):
        i = 0
        while True:
            i = d.find(sig, i)
            if i < 0: break
            start = i
            i += 1
            if start + 36 > n: continue
            ln = struct.unpack_from('<I', d, start + 4)[0]
            rev = d[start + 8]
            if not (36 <= ln <= 0x200000) or start + ln > n:
                continue
            csum = sum(d[start:start+ln]) & 0xFF
            oem = d[start+10:start+16]
            otbl = d[start+16:start+22]
            cid = d[start+26:start+30]
            # OEM id should be printable-ish ASCII
            printable = all(32 <= c <= 126 or c == 0 for c in oem)
            out.append(dict(sig=sig.decode(), off=start, len=ln, rev=rev,
                            csum=csum, oem=oem, otbl=otbl, cid=cid,
                            printable=printable, valid=(csum == 0)))
    out.sort(key=lambda x: x['off'])
    return out


def main():
    path = sys.argv[1]
    d = open(path, 'rb').read()
    ts = tables(d)
    print('file %s  %d bytes' % (path, len(d)))
    for t in ts:
        print('  @0x%-9X %-5s len=0x%-7X(%-8d) rev=%-3d csum=%02X %s oem=%-8r otbl=%-8r cid=%-6r' % (
            t['off'], t['sig'], t['len'], t['len'], t['rev'], t['csum'],
            'OK ' if t['valid'] else 'BAD', t['oem'], t['otbl'], t['cid']))
    good = [t for t in ts if t['sig'] == 'DSDT' and t['valid'] and t['printable']]
    print()
    print('valid DSDT candidates: %d' % len(good))
    for t in good:
        print('   off=0x%X len=%d oem=%r' % (t['off'], t['len'], t['oem']))


main()
