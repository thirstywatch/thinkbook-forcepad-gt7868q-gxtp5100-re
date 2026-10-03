#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""find Name()/Method()/Field definitions of given 4-char ACPI names."""
import struct, sys
sys.path.insert(0, '.')
from dump_aml import render, pkglen, namestr, NAME4

path = sys.argv[1]
names = sys.argv[2].split(',')
d = open(path, 'rb').read()

for nm in names:
    b = nm.encode()
    assert len(b) == 4
    print('===== %s =====' % nm)
    # Name definition
    for pat, label in ((b'\x08' + b, 'Name'), (b'\x14', 'Method'), (b'\x5b\x84' + b, 'Method2')):
        i = 0
        while True:
            i = d.find(pat, i)
            if i < 0: break
            st = i
            if label == 'Name':
                val, r = render(d, st + 5)
                print('  @0x%-7X Name(%-5s) = %s' % (st, nm, val))
                i += 1
                continue
            i += 1
    # Field element occurrences (raw)
    i = 0; cnt = 0
    while True:
        i = d.find(b, i)
        if i < 0: break
        cnt += 1
        if cnt <= 10:
            print('  occ @0x%-7X prev8=%s' % (i, d[max(0,i-8):i].hex()))
        i += 1
    print('  total occurrences: %d' % cnt)
    print()
