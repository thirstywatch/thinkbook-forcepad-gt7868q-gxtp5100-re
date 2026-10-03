#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aml_scan.py -- minimal ACPI AML walker.

* enumerates Device / Scope / Method / Name / OperationRegion / Field nodes with
  their exact byte extents (PkgLength is honoured)
* can report the innermost Device enclosing any given offset
* can render simple Name() payloads: integers, strings, buffers, packages
  (recursively, including named references)
"""
import struct, sys

UP = {0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E', 0x46: 'F', 0x47: 'G',
      0x48: 'H', 0x49: 'I', 0x4A: 'J', 0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N',
      0x4F: 'O', 0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T', 0x55: 'U',
      0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y', 0x5A: 'Z', 0x5F: '_'}
DIG = {c: chr(c) for c in range(0x30, 0x3A)}


def parse_pkglen(d, p):
    b0 = d[p]
    n = b0 >> 6
    if n == 0:
        return (b0 & 0x3F), 1
    if n == 1:
        return ((b0 & 0x0F) | (d[p+1] << 4)), 2
    if n == 2:
        return ((b0 & 0x0F) | (d[p+1] << 4) | (d[p+2] << 12)), 3
    return ((b0 & 0x0F) | (d[p+1] << 4) | (d[p+2] << 12) | (d[p+3] << 20)), 4


def name_string(d, p):
    segs = []
    if d[p] == 0x5C:      # RootChar
        segs.append('\\'); p += 1
    elif d[p] == 0x5E:    # ParentPrefixChar
        while d[p] == 0x5E:
            segs.append('^'); p += 1
    if d[p] == 0x00:      # NullName
        return ''.join(segs) or '<null>', p + 1
    if d[p] == 0x2E:      # DualNamePath
        p += 1
        s1, p = name_string(d, p)
        s2, p = name_string(d, p)
        return ''.join(segs) + s1 + '.' + s2, p
    if d[p] == 0x2F:      # MultiNamePath
        p += 1
        cnt = d[p]; p += 1
        parts = []
        for _ in range(cnt):
            s, p = name_string(d, p)
            parts.append(s)
        return ''.join(segs) + '.'.join(parts), p
    s = ''.join(UP.get(d[p+i], DIG.get(d[p+i], '?')) for i in range(4))
    return ''.join(segs) + s, p + 4


def render(d, p, depth=0, limit=8):
    """render a DataRefObject / TermArg briefly"""
    if p >= len(d) or depth > 6:
        return '...', p
    op = d[p]
    if op == 0x00: return 'Zero', p+1
    if op == 0x01: return 'One', p+1
    if op == 0xFF: return 'Ones', p+1
    if op == 0x0A: return '%d (0x%X)' % (d[p+1], d[p+1]), p+2
    if op == 0x0B:
        v = struct.unpack_from('<H', d, p+1)[0]; return '0x%X' % v, p+3
    if op == 0x0C:
        v = struct.unpack_from('<I', d, p+1)[0]; return '0x%X' % v, p+5
    if op == 0x0E:
        v = struct.unpack_from('<Q', d, p+1)[0]; return '0x%X' % v, p+9
    if op == 0x0D:
        s = bytearray()
        i = p+1
        while i < len(d) and d[i] != 0:
            s.append(d[i]); i += 1
        return '"%s"' % s.decode('latin1'), i+1
    if op == 0x11 or op == 0x12:      # Buffer / Package
        pkglen, nb = parse_pkglen(d, p+1)
        end = p+1+pkglen
        kind = 'Buffer' if op == 0x11 else 'Package'
        if op == 0x11:
            raw = d[p+1+nb:end]
            return 'Buffer(%d) %s%s' % (len(raw), raw[:48].hex(),
                                        '...' if len(raw) > 48 else ''), end
        cnt = d[p+1+nb]
        q = p+1+nb+1
        items = []
        for _ in range(min(cnt, limit)):
            if q >= end: break
            s, q = render(d, q, depth+1, limit)
            items.append(s)
        if cnt > limit: items.append('...+%d' % (cnt-limit))
        return 'Package(%d){%s}' % (cnt, ', '.join(items)), end
    if op == 0x5B and p+1 < len(d) and d[p+1] == 0x30:   # RevisionOp -> actually 5B 30 is not valid here
        return 'Rev', p+2
    if op in UP or op == 0x5C or op == 0x5E or op == 0x2E or op == 0x2F:
        s, q = name_string(d, p)
        return s, q
    if op == 0x5B and p+1 < len(d) and d[p+1] == 0x31:
        return 'DebugObj', p+2
    return 'op%02X' % op, p+1


def walk(d, start, end, depth, out, path):
    p = start
    while p < end:
        op = d[p]
        if op == 0x5B and p+1 < end:
            op2 = d[p+1]
            if op2 == 0x82:                       # Device
                pkglen, nb = parse_pkglen(d, p+2)
                de = p+2+pkglen
                nm, q = name_string(d, p+2+nb)
                out.append(dict(kind='Device', name=nm, start=p, hdr_end=q,
                                end=de, depth=depth, path=path))
                walk(d, q, de, depth+1, out, path + '/' + nm)
                p = de; continue
            if op2 == 0x83:                       # Processor
                pkglen, nb = parse_pkglen(d, p+2)
                de = p+2+pkglen
                nm, q = name_string(d, p+2+nb)
                out.append(dict(kind='Processor', name=nm, start=p, hdr_end=q+6,
                                end=de, depth=depth, path=path))
                walk(d, q+6, de, depth+1, out, path + '/' + nm)
                p = de; continue
            if op2 == 0x84:                       # PowerResource
                pkglen, nb = parse_pkglen(d, p+2)
                de = p+2+pkglen
                nm, q = name_string(d, p+2+nb)
                out.append(dict(kind='PowerRes', name=nm, start=p, hdr_end=q+3,
                                end=de, depth=depth, path=path))
                walk(d, q+3, de, depth+1, out, path + '/' + nm)
                p = de; continue
            if op2 == 0x85:                       # ThermalZone
                pkglen, nb = parse_pkglen(d, p+2)
                de = p+2+pkglen
                nm, q = name_string(d, p+2+nb)
                out.append(dict(kind='ThermalZone', name=nm, start=p, hdr_end=q,
                                end=de, depth=depth, path=path))
                walk(d, q, de, depth+1, out, path + '/' + nm)
                p = de; continue
            if op2 in (0x80, 0x81, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x8B):
                pkglen, nb = parse_pkglen(d, p+2)
                p = p+2+pkglen; continue
            p += 1; continue
        if op == 0x10:                            # Scope
            pkglen, nb = parse_pkglen(d, p+1)
            se = p+1+pkglen
            nm, q = name_string(d, p+1+nb)
            out.append(dict(kind='Scope', name=nm, start=p, hdr_end=q,
                            end=se, depth=depth, path=path))
            walk(d, q, se, depth+1, out, path + '/' + nm)
            p = se; continue
        if op == 0x14:                            # Method
            pkglen, nb = parse_pkglen(d, p+1)
            me = p+1+pkglen
            nm, q = name_string(d, p+1+nb)
            out.append(dict(kind='Method', name=nm, start=p, hdr_end=q+1,
                            end=me, depth=depth, path=path))
            p = me; continue
        if op == 0x08:                            # Name
            nm, q = name_string(d, p+1)
            val, r = render(d, q, 0, 12)
            out.append(dict(kind='Name', name=nm, start=p, hdr_end=q, end=r,
                            depth=depth, path=path, value=val))
            p = r; continue
        if op == 0x15:                            # External
            nm, q = name_string(d, p+1)
            out.append(dict(kind='External', name=nm, start=p, hdr_end=q,
                            end=q+2, depth=depth, path=path))
            p = q+2; continue
        if op == 0x5B and p+1 < end and d[p+1] == 0x02:   # Alias
            p += 2; continue
        p += 1


if __name__ == '__main__':
    path = sys.argv[1]
    d = open(path, 'rb').read()
    body_start = 36
    out = []
    walk(d, body_start, len(d), 0, out, '')
    print('nodes: %d' % len(out))
    for q in sys.argv[2:]:
        target = int(q, 0)
        cands = [n for n in out if n['start'] <= target < n['end'] and n['kind'] in ('Device', 'Scope', 'ThermalZone', 'PowerRes', 'Processor')]
        cands.sort(key=lambda n: n['start'])
        print('\n--- innermost containers for 0x%X ---' % target)
        for n in cands:
            print('   %-12s %-40s 0x%X..0x%X (len %d) depth=%d' % (
                n['kind'], n['path'] + '/' + n['name'], n['start'], n['end'],
                n['end']-n['start'], n['depth']))
        # innermost Device
        devs = [n for n in cands if n['kind'] == 'Device']
        if devs:
            dev = devs[-1]
            print('   >>> innermost Device: %s%s  0x%X..0x%X len=%d' % (
                dev['path'], '/' + dev['name'], dev['start'], dev['end'], dev['end']-dev['start']))
