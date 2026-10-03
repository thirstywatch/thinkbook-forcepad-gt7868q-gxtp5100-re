#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dump_aml.py -- hex dump (with ASCII) of a byte range, plus a best-effort
AML line listing (Name / Method / OpRegion / Field / Device / Scope) for the range.
"""
import struct, sys

UP = set(range(0x41, 0x5B)) | {0x5F}
DIG = set(range(0x30, 0x3A))
NAME4 = UP | DIG


def pkglen(d, p):
    b0 = d[p]; n = b0 >> 6
    if n == 0: return (b0 & 0x3F), 1
    if n == 1: return ((b0 & 0x0F) | (d[p+1] << 4)), 2
    if n == 2: return ((b0 & 0x0F) | (d[p+1] << 4) | (d[p+2] << 12)), 3
    return ((b0 & 0x0F) | (d[p+1] << 4) | (d[p+2] << 12) | (d[p+3] << 20)), 4


def namestr(d, p):
    s = ''
    if d[p] == 0x5C: s += '\\'; p += 1
    elif d[p] == 0x5E:
        while d[p] == 0x5E: s += '^'; p += 1
    if d[p] == 0x00: return s or '<null>', p+1
    if d[p] == 0x2E:
        p += 1
        for k in range(2):
            s += d[p:p+4].decode('ascii') + ('.' if k == 0 else ''); p += 4
        return s, p
    if d[p] == 0x2F:
        p += 1; cnt = d[p]; p += 1
        parts = []
        for _ in range(cnt):
            parts.append(d[p:p+4].decode('ascii')); p += 4
        return s + '.'.join(parts), p
    return s + d[p:p+4].decode('ascii'), p+4


def render(d, p, depth=0):
    if depth > 7 or p >= len(d): return '...', p
    op = d[p]
    if op == 0x00: return 'Zero', p+1
    if op == 0x01: return 'One', p+1
    if op == 0xFF: return 'Ones', p+1
    if op == 0x0A: return '0x%X' % d[p+1], p+2
    if op == 0x0B: return '0x%X' % struct.unpack_from('<H', d, p+1)[0], p+3
    if op == 0x0C: return '0x%X' % struct.unpack_from('<I', d, p+1)[0], p+5
    if op == 0x0E: return '0x%X' % struct.unpack_from('<Q', d, p+1)[0], p+9
    if op == 0x0D:
        i = p+1; b = bytearray()
        while i < len(d) and d[i] != 0: b.append(d[i]); i += 1
        return '"%s"' % b.decode('latin1'), i+1
    if op in (0x11, 0x12):
        l, nb = pkglen(d, p+1); end = p+1+l
        if op == 0x11:
            raw = d[p+1+nb:end]
            return 'Buffer[%d] %s' % (len(raw), raw.hex()), end
        cnt = d[p+1+nb]; q = p+1+nb+1
        items = []
        for _ in range(min(cnt, 24)):
            if q >= end: break
            s, q = render(d, q, depth+1)
            items.append(s)
        if cnt > 24: items.append('...(+%d)' % (cnt-24))
        return 'Package(%d) { %s }' % (cnt, ', '.join(items)), end
    if op in NAME4 or op in (0x5C, 0x5E, 0x2E, 0x2F):
        return namestr(d, p)
    if op == 0x5B and d[p+1] in (0x30, 0x31): return 'Rev/Debug', p+2
    if op == 0x5B and d[p+1] == 0x80:
        l, nb = pkglen(d, p+2); return 'OpRegion', p+2+l
    return 'op%02X' % op, p+1


def lines(d, start, end):
    out = []
    p = start
    while p < end:
        op = d[p]
        try:
            if op == 0x08:
                nm, q = namestr(d, p+1)
                if all(c in NAME4 for c in d[p+1:p+5]):
                    val, r = render(d, q)
                    if r <= end:
                        out.append('0x%06X  Name(%-8s) = %s' % (p, nm, val))
                        p = r; continue
            if op == 0x14:
                l, nb = pkglen(d, p+1); me = p+1+l
                if me <= end:
                    nm, q = namestr(d, p+1+nb)
                    out.append('0x%06X  Method(%s, flags=0x%X)   len=%d' % (p, nm, d[q], me-p))
                    p = me; continue
            if op == 0x5B and d[p+1] == 0x80:
                l, nb = pkglen(d, p+2); oe = p+2+l
                if oe <= end:
                    nm, q = namestr(d, p+2+nb)
                    space = d[q]
                    out.append('0x%06X  OperationRegion(%s, space=0x%X, off=%s, len=%s)' % (
                        p, nm, space, *[render(d, q+1+i)[0] for i in (0, 0)]))
                    p = oe; continue
            if op == 0x5B and d[p+1] == 0x81:
                l, nb = pkglen(d, p+2); fe = p+2+l
                if fe <= end:
                    nm, q = namestr(d, p+2+nb)
                    out.append('0x%06X  Field(%s, flags=0x%X)  len=%d' % (p, nm, d[q], fe-p))
                    p = fe; continue
            if op == 0x5B and d[p+1] == 0x82:
                l, nb = pkglen(d, p+2); de = p+2+l
                if de <= end:
                    nm, q = namestr(d, p+2+nb)
                    out.append('0x%06X  Device(%s)  len=%d' % (p, nm, de-p))
                    p = de; continue
            if op == 0x10:
                l, nb = pkglen(d, p+1); se = p+1+l
                if se <= end:
                    nm, q = namestr(d, p+1+nb)
                    out.append('0x%06X  Scope(%s)  len=%d' % (p, nm, se-p))
                    p = se; continue
            if op == 0x5B and d[p+1] == 0x84:
                l, nb = pkglen(d, p+2); me = p+2+l
                if me <= end:
                    nm, q = namestr(d, p+2+nb)
                    out.append('0x%06X  Method(%s, flags=0x%X)  len=%d' % (p, nm, d[q], me-p))
                    p = me; continue
        except Exception:
            pass
        p += 1
    return out


if __name__ == '__main__':
    path = sys.argv[1]
    lo = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3], 0) if len(sys.argv) > 3 else len(open(path, 'rb').read())
    d = open(path, 'rb').read()
    print('### AML listing 0x%X..0x%X' % (lo, hi))
    for l in lines(d, lo, hi):
        print(l)
    print()
    print('### hex dump')
    for a in range(lo, hi, 16):
        chunk = d[a:a+16]
        print('%06X  %-47s  %s' % (a, ' '.join('%02X' % b for b in chunk),
                                   ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)))
