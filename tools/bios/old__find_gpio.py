#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_gpio.py -- enumerate every GPIO connection descriptor (tag 0x8C) in a blob and
print its connection type, interrupt/IO flags, pin table values and resource source.

Layout used (verified against the X9-15 DSDT, offsets from the descriptor start):
  [0]      RevisionId
  [1]      ConnectionType      0x00 = GpioIo, 0x01 = GpioInt
  [2..3]   GeneralFlags
  [4..5]   IntFlags / IoFlags
  [6]      PinConfiguration
  [7..8]   OutputDriveStrength
  [9..10]  DebounceTimeout
  [11..12] PinTableOffset      (u16, from descriptor start)
  [13]     ResourceSourceIndex
  [14..15] VendorDataOffset
  [16..17] VendorDataLength
  [18..19] reserved
  [20..21] first pin (u16)     -- == bytes at descriptor_start + PinTableOffset
  [22..]   ResourceSource string (NUL terminated)
"""
import struct, sys

CT = {0x00: 'GpioIo ', 0x01: 'GpioInt'}
POL = {0: 'ActiveHigh', 1: 'ActiveLow'}
MODE = {0: 'Level', 1: 'Edge'}


def scan(d, label):
    print('==== %s ====' % label)
    n = 0
    i = 0
    hits = []
    while True:
        i = d.find(b'\x8c', i)
        if i < 0: break
        if i + 3 > len(d):
            break
        ln = struct.unpack_from('<H', d, i+1)[0]
        if not (20 <= ln <= 80) or i + 3 + ln > len(d):
            i += 1
            continue
        body = d[i+3:i+3+ln]
        ctype = body[1]
        if ctype not in (0, 1):
            i += 1
            continue
        gflags = struct.unpack_from('<H', body, 2)[0]
        iflags = struct.unpack_from('<H', body, 4)[0]
        ptoff = struct.unpack_from('<H', body, 11)[0]
        rsi = body[13]
        vdoff = struct.unpack_from('<H', body, 14)[0]
        vdlen = struct.unpack_from('<H', body, 16)[0]
        # resource source string: find first printable run ending with 0
        s = body.find(b'\x5c')      # backslash of an ACPI path
        if s < 0:
            s = vdoff - 3 if 3 <= vdoff - 3 < len(body) else -1
        src = ''
        if 0 <= s < len(body):
            e = body.find(b'\x00', s)
            if e < 0: e = len(body)
            src = body[s:e].decode('latin1', 'replace')
        pins = []
        p = ptoff - 3 if ptoff >= 3 else ptoff
        while 0 <= p and p + 2 <= len(body) and len(pins) < 8:
            pins.append(struct.unpack_from('<H', body, p)[0])
            p += 2
            if p == s:
                break
        n += 1
        hits.append((i, ctype, gflags, iflags, pins, src, ln))
        i += 1
    for i, ctype, gflags, iflags, pins, src, ln in hits:
        mode = MODE.get(iflags & 1, '?')
        pol = POL.get((iflags >> 1) & 1, '?')
        share = 'Exclusive' if not ((iflags >> 2) & 1) else 'Shared'
        wake = 'Wake' if (iflags >> 4) & 1 else ''
        print('  @0x%-8X %s len=%-3d genflags=0x%04X intflags=0x%04X [%s/%s/%s %s] pins=%s src=%r' % (
            i, CT[ctype], ln, gflags, iflags, mode, pol, share, wake,
            [hex(x) for x in pins], src))
    print('  total: %d\n' % n)
    return hits


if __name__ == '__main__':
    for p in sys.argv[1:]:
        scan(open(p, 'rb').read(), p)
