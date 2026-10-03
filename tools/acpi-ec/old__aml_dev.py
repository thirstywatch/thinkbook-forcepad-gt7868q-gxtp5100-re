#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aml_dev.py -- robust AML Device / Method / Name finder by direct opcode scan
(no full recursive disassembly, so it cannot desynchronise).

* finds every 5B 82 (DeviceOp) whose PkgLength + NameString are well formed
* nests them purely by byte containment
* finds every 5B 84 (MethodOp) and 08 (NameOp) with a well formed NameString
"""
import struct, sys

UP = set(range(0x41, 0x5B)) | {0x5F}
DIG = set(range(0x30, 0x3A))
NAME4 = UP | DIG


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


def read_namestr(d, p):
    """returns (text, endpos) or (None, None)"""
    s = ''
    start = p
    if p < len(d) and d[p] == 0x5C:
        s += '\\'; p += 1
    elif p < len(d) and d[p] == 0x5E:
        while p < len(d) and d[p] == 0x5E:
            s += '^'; p += 1
    if p >= len(d):
        return None, None
    if d[p] == 0x00:
        return s or '<null>', p+1
    if d[p] == 0x2E:
        p += 1
        for k in range(2):
            if p+4 > len(d) or any(x not in NAME4 for x in d[p:p+4]):
                return None, None
            s += d[p:p+4].decode('ascii') + ('.' if k == 0 else '')
            p += 4
        return s, p
    if d[p] == 0x2F:
        p += 1
        if p >= len(d): return None, None
        cnt = d[p]; p += 1
        parts = []
        for k in range(cnt):
            if p+4 > len(d) or any(x not in NAME4 for x in d[p:p+4]):
                return None, None
            parts.append(d[p:p+4].decode('ascii')); p += 4
        return s + '.'.join(parts), p
    if p+4 > len(d) or any(x not in NAME4 for x in d[p:p+4]):
        return None, None
    return s + d[p:p+4].decode('ascii'), p+4


def scan_devices(d):
    devs = []
    i = 0
    n = len(d)
    while True:
        i = d.find(b'\x5b\x82', i)
        if i < 0: break
        try:
            pkglen, nb = parse_pkglen(d, i+2)
        except IndexError:
            i += 1; continue
        end = i + 2 + pkglen
        if pkglen < 8 or end > n:
            i += 1; continue
        nm, q = read_namestr(d, i+2+nb)
        if nm is None or q > end:
            i += 1; continue
        devs.append(dict(start=i, end=end, name=nm, hdr_end=q, pkglen=pkglen))
        i += 1
    return devs


def nest(devs):
    """assign parent index by smallest enclosing device"""
    devs.sort(key=lambda x: (x['start'], -x['end']))
    for k, a in enumerate(devs):
        parent = None
        for j, b in enumerate(devs):
            if j == k: continue
            if b['start'] <= a['start'] and a['end'] <= b['end'] and (b['start'], -b['end']) < (a['start'], -a['end']):
                if parent is None or (b['start'] > devs[parent]['start']):
                    parent = j
        a['parent'] = parent
    for k, a in enumerate(devs):
        path = []
        cur = k
        seen = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            path.append(devs[cur]['name'])
            cur = devs[cur]['parent']
        a['path'] = '/' + '/'.join(reversed(path))
    return devs


def scan_methods(d):
    out = []
    i = 0
    while True:
        i = d.find(b'\x5b\x84', i)
        if i < 0: break
        try:
            pkglen, nb = parse_pkglen(d, i+2)
        except IndexError:
            i += 1; continue
        end = i + 2 + pkglen
        if 9 <= pkglen and end <= len(d):
            nm, q = read_namestr(d, i+2+nb)
            if nm is not None and (q+1) <= end:
                out.append(dict(start=i, end=end, name=nm))
        i += 1
    return out


if __name__ == '__main__':
    path = sys.argv[1]
    d = open(path, 'rb').read()
    devs = nest(scan_devices(d))
    print('devices: %d' % len(devs))
    for q in sys.argv[2:]:
        t = int(q, 0)
        encl = [x for x in devs if x['start'] <= t < x['end']]
        encl.sort(key=lambda x: x['start'])
        print('\n=== offset 0x%X ===' % t)
        for x in encl:
            print('   %-46s 0x%X..0x%X  len=%-7d hdr=0x%X' % (
                x['path'], x['start'], x['end'], x['end']-x['start'], x['hdr_end']))
        if encl:
            dev = encl[-1]
            print('   >>> innermost Device %s  bytes 0x%X..0x%X  len=%d' % (
                dev['path'], dev['start'], dev['end'], dev['end']-dev['start']))
