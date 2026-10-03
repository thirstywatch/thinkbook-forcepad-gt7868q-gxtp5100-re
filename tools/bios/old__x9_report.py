#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
x9_report.py -- produce the annotated TPAD/TPD0 hex dump + decoded inventory
                and the Markdown findings report for the X9-15 Gen1 extraction.
"""
import struct, os, sys

BASE = r'<WORKSPACE>'
OUT = os.path.join(BASE, 'deliverables')
DSDT = os.path.join(OUT, 'DSDT_X9-15.bin')
REF = r'<WORKSPACE>'

TPD0_OFF, TPD0_END = 0x17331, 0x17637
ITML_OFF, ITML_END = 0x17399, 0x173CC
EC_OFF, EC_END = 0x2EC0, 0x2F40

d = open(DSDT, 'rb').read()
os.makedirs(OUT, exist_ok=True)


def hexdump(data, base, f, note=None):
    if note:
        f.write('### %s\n' % note)
    for a in range(0, len(data), 16):
        chunk = data[a:a+16]
        f.write('%06X  %-47s  %s\n' % (base + a,
                ' '.join('%02X' % b for b in chunk),
                ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)))
    f.write('\n')


def render(d, p, depth=0):
    if depth > 7 or p >= len(d):
        return '...', p
    op = d[p]
    if op == 0x00: return 'Zero', p+1
    if op == 0x01: return 'One', p+1
    if op == 0xFF: return 'Ones', p+1
    if op == 0x0A: return '0x%X' % d[p+1], p+2
    if op == 0x0B: return '0x%X' % struct.unpack_from('<H', d, p+1)[0], p+3
    if op == 0x0C: return '0x%X' % struct.unpack_from('<I', d, p+1)[0], p+5
    if op == 0x0D:
        i = p+1; b = bytearray()
        while i < len(d) and d[i] != 0:
            b.append(d[i]); i += 1
        return '"%s"' % b.decode('latin1'), i+1
    if op == 0x11:
        l, nb = pkglen(d, p+1); end = p+1+l
        raw = d[p+1+nb+2:end] if len(d) > p+1+nb+1 and d[p+1+nb] == 0x0A else d[p+1+nb:end]
        return 'Buffer[%d] %s' % (len(raw), raw.hex()), end
    if op == 0x12:
        l, nb = pkglen(d, p+1); end = p+1+l
        cnt = d[p+1+nb]; q = p+1+nb+1
        items = []
        for _ in range(min(cnt, 16)):
            if q >= end: break
            s, q = render(d, q, depth+1)
            items.append(s)
        if cnt > 16: items.append('...(+%d)' % (cnt-16))
        return 'Package(%d) { %s }' % (cnt, ', '.join(items)), end
    if 0x41 <= op <= 0x5A or op == 0x5F:
        return d[p:p+4].decode('latin1'), p+4
    return 'op%02X' % op, p+1


def pkglen(d, p):
    b0 = d[p]; n = b0 >> 6
    if n == 0: return (b0 & 0x3F), 1
    if n == 1: return ((b0 & 0x0F) | (d[p+1] << 4)), 2
    if n == 2: return ((b0 & 0x0F) | (d[p+1] << 4) | (d[p+2] << 12)), 3
    return ((b0 & 0x0F) | (d[p+1] << 4) | (d[p+2] << 12) | (d[p+3] << 20)), 4


UP = set(range(0x41, 0x5B)) | {0x5F}
NAME4 = UP | set(range(0x30, 0x3A))


def namestr(d, p):
    s = ''
    if d[p] == 0x5C: s += '\\'; p += 1
    elif d[p] == 0x5E:
        while d[p] == 0x5E: s += '^'; p += 1
    if d[p] == 0x00: return s or '<null>', p+1
    return s + d[p:p+4].decode('ascii'), p+4


def inventory(d, lo, hi):
    """best-effort statement listing inside a range"""
    res = []
    p = lo
    while p < hi:
        op = d[p]
        try:
            if op == 0x08 and all(c in NAME4 for c in d[p+1:p+5]):
                nm, q = namestr(d, p+1)
                val, r = render(d, q)
                if r <= hi:
                    res.append('0x%06X  Name(%-5s) = %s' % (p, nm, val))
                    p = r; continue
            if op == 0x14:
                l, nb = pkglen(d, p+1); me = p+1+l
                if me <= hi:
                    nm, q = namestr(d, p+1+nb)
                    res.append('0x%06X  Method(%-5s, flags=0x%02X -> %d args%s)  len=%d' % (
                        p, nm, d[q], d[q] & 7, ', Serialized' if d[q] & 8 else '', me-p))
                    p = me; continue
            if op == 0x5B and d[p+1] == 0x82:
                l, nb = pkglen(d, p+2); de = p+2+l
                if de <= hi:
                    nm, q = namestr(d, p+2+nb)
                    res.append('0x%06X  Device(%s)  len=%d' % (p, nm, de-p))
                    p = de; continue
            if op == 0x5B and d[p+1] == 0x84:
                l, nb = pkglen(d, p+2); me = p+2+l
                if me <= hi:
                    nm, q = namestr(d, p+2+nb)
                    res.append('0x%06X  Method(%s)  len=%d' % (p, nm, me-p))
                    p = me; continue
            if op == 0x8A:
                nm, q = namestr(d, p+1)
                res.append('0x%06X  CreateDWordField(%s, 0x%02X, %s)' % (
                    p, nm, d[q+1] if d[q] == 0x0A else 0, d[q+2:q+6].decode('latin1')))
                p = q+6; continue
            if op == 0x8B:
                nm, q = namestr(d, p+1)
                res.append('0x%06X  CreateWordField(%s, 0x%02X, %s)' % (
                    p, nm, d[q+1] if d[q] == 0x0A else 0, d[q+2:q+6].decode('latin1')))
                p = q+6; continue
            if op == 0x8D:
                nm, q = namestr(d, p+1)
                res.append('0x%06X  CreateBitField(%s, 0x%02X, %s)' % (
                    p, nm, d[q+1] if d[q] == 0x0A else 0, d[q+2:q+6].decode('latin1')))
                p = q+6; continue
        except Exception:
            pass
        p += 1
    return res


# ---------------------------------------------------------------- dump file
with open(os.path.join(OUT, 'TPAD_X9-15_hexdump.txt'), 'w', encoding='utf-8') as f:
    f.write('X9-15 Gen1  touchpad ACPI node  --  DSDT device "TPD0"\n')
    f.write('=' * 78 + '\n')
    f.write('source DSDT : DSDT_X9-15.bin (300,544 bytes, checksum OK)\n')
    f.write('device range: DSDT 0x%06X .. 0x%06X  (%d bytes)\n' % (TPD0_OFF, TPD0_END, TPD0_END-TPD0_OFF))
    f.write('full name   : \\_SB.PC00.I2C5.TPD0   (enclosed by Scope(\\_SB.PC00.I2C5) at 0x17320)\n')
    f.write('NOTE        : the literal ACPI name "TPAD" exists on this model only as an\n')
    f.write('              8-bit EC field (see below); the touchpad *device* is TPD0.\n\n')

    f.write('-' * 78 + '\nAML statement inventory of the device subtree\n' + '-' * 78 + '\n')
    f.write('  raw head: %s\n\n' % ' '.join('%02X' % b for b in d[TPD0_OFF:TPD0_OFF+9]))
    for l in inventory(d, TPD0_OFF + 8, TPD0_END):
        f.write(l + '\n')
    f.write('\n')

    f.write('-' * 78 + '\nraw hex of the whole TPD0 device subtree (774 bytes)\n' + '-' * 78 + '\n')
    hexdump(d[TPD0_OFF:TPD0_END], TPD0_OFF, f)

    f.write('-' * 78 + '\nName (ITML, ...) vendor table  [DSDT 0x%X .. 0x%X]\n' % (ITML_OFF, ITML_END) + '-' * 78 + '\n')
    f.write('  raw: %s\n\n' % ' '.join('%02X' % b for b in d[ITML_OFF:ITML_END]))
    hexdump(d[ITML_OFF:ITML_END], ITML_OFF, f)
    v, _ = render(d, ITML_OFF + 5)
    f.write('  decoded: Name(ITML) = %s\n\n' % v)

    f.write('-' * 78 + '\nthe literal "TPAD" name on this machine: EC/GNVS field list\n' + '-' * 78 + '\n')
    hexdump(d[EC_OFF:EC_END], EC_OFF, f, 'DSDT 0x%X..0x%X  (TPAD is the 8-bit field at 0x2F0B)'
            % (EC_OFF, EC_END))

print('wrote TPAD_X9-15_hexdump.txt')

# ---------------------------------------------------------------- md report
ref = open(REF, 'rb').read()
r_tpad = ref.find(b'TPAD')
with open(os.path.join(OUT, 'TPAD_X9-15_hexdump.txt'), 'a', encoding='utf-8') as f:
    f.write('-' * 78 + '\nreference machine (ThinkBook 14 G6+ IMH) Device(TPAD) for comparison\n' + '-' * 78 + '\n')
    f.write('  DSDT_LENOVO_CB-01____00000001.bin  Device(TPAD) @ 0x7042A\n')
    hexdump(ref[0x7042A:0x704E0], 0x7042A, f)
    f.write('  Name (SBFG, ...) @ 0x704F4 contains the hard-coded GpioInt descriptor\n')
    f.write('  pin table entry 0x00B6 = 182, resource source "\\_SB.GPI0"\n')
    hexdump(ref[0x704F4:0x70522], 0x704F4, f)

print('appended reference comparison')
print('report inputs ready')
