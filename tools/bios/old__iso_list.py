#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISO9660 (+ El Torito) lister for the Lenovo X9-15 Gen1 BIOS CD image."""
import struct, sys, os

def rd(f, off, n):
    f.seek(off); return f.read(n)

def u32(b, o=0): return struct.unpack_from('<I', b, o)[0]
def u16(b, o=0): return struct.unpack_from('<H', b, o)[0]

def rock_ridge_name(rec):
    """parse SUSP/RockRidge NM entry from a directory record's system-use area"""
    su_off = 33 + rec[32]
    su_len = len(rec) - su_off
    if su_len <= 0: return None
    p = su_off
    name = b''
    while p + 4 <= len(rec) and rec[p:p+2] in (b'NM', b'PX', b'TF', b'SL', b'RE', b'CL', b'PL', b'RR', b'SP', b'CE', b'ER', b'ST'):
        sig = rec[p:p+2]; ln = rec[p+2]; ver = rec[p+3]
        if ln < 4: break
        body = rec[p+4:p+ln]
        if sig == b'NM' and body:
            flags = body[0]
            if not (flags & 0x06):  # not '.' or '..'
                name += body[1:]
        p += ln
    return name.decode('utf-8', 'replace') if name else None

def walk(f, extent_sector, size, base, out, depth, seen):
    key = (extent_sector, size)
    if key in seen or depth > 12: return
    seen.add(key)
    off = extent_sector * 2048
    data = rd(f, off, size)
    p = 0
    while p < len(data):
        rlen = data[p]
        if rlen == 0:
            p = ((p // 2048) + 1) * 2048
            if p >= len(data): break
            continue
        rec = data[p:p+rlen]
        if len(rec) < 33: break
        ext_lba = u32(rec, 2)
        dsize = u32(rec, 10)
        flags = rec[25]
        namelen = rec[32]
        name = rec[33:33+namelen]
        p += rlen
        if namelen == 1 and name in (b'\x00', b'\x01'):
            continue
        nm = name.decode('ascii', 'replace')
        if nm.endswith(';1'): nm = nm[:-2]
        rr = rock_ridge_name(rec)
        label = rr if rr else nm
        isdir = bool(flags & 0x02)
        out.append((depth, label, ext_lba, dsize, isdir))
        if isdir:
            walk(f, ext_lba, dsize, base, out, depth+1, seen)

def main():
    path = sys.argv[1]
    outpath = sys.argv[2] if len(sys.argv) > 2 else None
    with open(path, 'rb') as f:
        pvd = rd(f, 16*2048, 2048)
        assert pvd[1:6] == b'CD001', 'not ISO9660'
        root = pvd[156:156+34]
        root_lba = u32(root, 2); root_size = u32(root, 10)
        out = []
        walk(f, root_lba, root_size, 0, out, 0, set())
        lines = []
        for depth, label, lba, size, isdir in out:
            lines.append('%s%-60s lba=%-8d off=0x%-10X size=%-10d %s' % (
                '  '*depth + ('[D] ' if isdir else '    '), label, lba, lba*2048, size,
                'DIR' if isdir else ''))
        txt = '\n'.join(lines)
        print(txt)
        if outpath:
            open(outpath, 'w', encoding='utf-8').write(txt)
        # El Torito boot catalog
        bvd = rd(f, 17*2048, 2048)
        print('\n--- Boot Record Volume Descriptor ---')
        print('id', bvd[1:6], 'boot sys id', bvd[7:39])
        cat_lba = u32(bvd, 0x47)
        print('boot catalog LBA', cat_lba, hex(cat_lba*2048))
        cat = rd(f, cat_lba*2048, 2048)
        print('catalog[0:32]', cat[0:32].hex())
        n = u16(cat, 0x1E)
        print('entries', n)
        for i in range(min(n, 8)):
            e = cat[32+i*32: 32+(i+1)*32]
            if len(e) < 32: break
            bootable = e[0]
            media = e[1]
            load_seg = u16(e, 2); systype = e[4]
            sect = u16(e, 6); img_lba = u32(e, 8); img_len = u32(e, 12)
            print(' entry%d bootable=%02X media=%02X loadseg=%04X systype=%02X sect=%d imgLBA=%d off=0x%X len=%d(0x%X)' % (
                i, bootable, media, load_seg, systype, sect, img_lba, img_lba*2048, img_len, img_len))

main()
