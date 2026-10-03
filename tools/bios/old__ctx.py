#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List every occurrence of a marker with context, and validate nearby ACPI tables."""
import struct, sys

path = sys.argv[1]
markers = sys.argv[2].split(',') if len(sys.argv) > 2 else ['DSDT', 'TPAD']
d = open(path, 'rb').read()
print('file %s  %d bytes' % (path, len(d)))
for m in markers:
    b = m.encode()
    i = 0
    n = 0
    while True:
        i = d.find(b, i)
        if i < 0: break
        n += 1
        ln = struct.unpack_from('<I', d, i+4)[0] if i+8 < len(d) else 0
        ctx = d[max(0, i-8):i+24]
        print('  %-6s #%-3d @0x%-9X prev=%s hdrlen=0x%X ctx=%s' % (
            m, n, i, d[i-4:i].hex() if i >= 4 else '', ln,
            ' '.join('%02X' % x for x in ctx)))
        i += 1
    print('  total %s = %d\n' % (m, n))
