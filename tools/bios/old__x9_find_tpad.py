#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
x9_find_tpad.py -- scan raw images for TPAD Device nodes and touchpad vendor strings.

Device pattern: 5B 82 <PkgLen(1-4 bytes)> 54 50 41 44 ("TPAD")
PkgLength encoding: first byte, if bits 6-7 == 0 -> 1 byte; == 0x40 -> 2 bytes;
                    0x80 -> 3 bytes; 0xC0 -> 4 bytes (low nibble = extra bytes count)
"""
import sys, struct

MARKERS = [b'GXTP5100', b'TPID', b'SYNA2BA6', b'ELAN06FA', b'CIRQ1080', b'SYNA',
           b'ELAN06', b'TPAD', b'ETPD', b'TPDT']


def scan(path):
    d = open(path, 'rb').read()
    print('==== %s  (%d bytes) ====' % (path, len(d)))
    for m in MARKERS:
        i = 0; n = 0; offs = []
        while True:
            i = d.find(m, i)
            if i < 0: break
            n += 1
            if len(offs) < 12: offs.append('0x%X' % i)
            i += 1
        if n:
            print('   %-10s x%-4d %s' % (m.decode(), n, ' '.join(offs)))
    # TPAD device nodes
    i = 0; n = 0
    print('   --- TPAD Device nodes (5B 82 .. TPAD) ---')
    while True:
        i = d.find(b'\x5b\x82', i)
        if i < 0: break
        for ext in range(0, 4):
            if d[i+2+ext:i+6+ext] == b'TPAD':
                pkg = d[i+2]
                print('      dev @0x%X pkglen=0x%X: %s' % (
                    i, pkg, ' '.join('%02X' % b for b in d[i:i+0x20])))
                n += 1
                break
        i += 1
    print('   TPAD device nodes: %d' % n)
    print()


for p in sys.argv[1:]:
    scan(p)
