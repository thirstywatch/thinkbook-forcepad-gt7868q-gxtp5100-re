#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick signature census over a set of files."""
import sys, os

SIGS = [b'_FVH', b'DSDT', b'FACP', b'SSDT', b'APIC', b'LZMA', b'\x25\x4e\x37\x7e',
        b'\x98\x58\xee\x4e', b'FL2', b'FL1', b'_FSV', b'EFI PART', b'NVAR',
        b'\x5d\x00\x00', b'\xfd7zXZ\x00', b'7z\xbc\xaf\x27\x1c']

for fn in sys.argv[1:]:
    d = open(fn, 'rb').read()
    print('=== %s  %d bytes (0x%X)' % (fn, len(d), len(d)))
    print('  head: %s' % d[:64].hex(' '))
    print('  tail: %s' % d[-32:].hex(' '))
    for s in SIGS:
        offs = []
        i = 0
        while True:
            i = d.find(s, i)
            if i < 0 or len(offs) >= 10: break
            offs.append('0x%X' % i); i += 1
        if offs:
            print('   %-14s cnt>=%-4d %s' % (s.decode('latin1'), len(offs), offs))
    print()
