#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
x9_fv.py -- UEFI firmware volume / FFS / section parser + recursive decompressor
           for the Lenovo ThinkPad X9-15 Gen1 BIOS payload ($0AN4C00.SC1/.SC2).

DataOffset semantics: EFI_GUID_DEFINED_SECTION.DataOffset is measured from the
start of the section (i.e. including the 4-byte EFI_COMMON_SECTION_HEADER).

Supported decompressors, tried in order:
  * LZMA "alone" framing  : 5 props + u64 size + raw stream
  * EDK2 LzmaCustomDecomp : u32 uncomp + 5 props + raw stream
  * bare 5 props + raw stream
  * EFI standard (Tiano)  : u32 uncomp + u8 algo + bitstream
  * raw deflate / zlib
"""
import struct, sys, os, lzma, zlib

FS2 = bytes.fromhex("78e58c8c3d8a1c4f9935896185c32dd3")

LZMA_GUID       = bytes.fromhex("9858ee4e14395942d69ede7bd79403cf")  # EE4E5898-3914-4259-9D6E-DC7BD79403CF
LZMAF86_GUID    = bytes.fromhex("f2d9d311a0e94ac29e3f3b4f8fb0e4a5")
ACPI_TABLE_GUID = bytes.fromhex("254e377e018eee4f87f2390c23c606cd")  # 7E374E25-8E01-4FEE-87F2-390C23C606CD

KNOWN_GUIDS = {
    LZMA_GUID:       'LZMA_COMPRESS',
    ACPI_TABLE_GUID: 'ACPI_TABLES_MODULE',
}

SEC_TYPES = {0x00: 'SEC_UNKNOWN', 0x01: 'COMPRESSION', 0x02: 'GUID_DEFINED',
             0x03: 'DISPOSABLE', 0x10: 'PE32', 0x11: 'PIC', 0x12: 'TE',
             0x13: 'DXE_DEPEX', 0x14: 'VERSION', 0x15: 'UI', 0x16: 'COMPAT16',
             0x17: 'FV_IMAGE', 0x18: 'FREEFORM_GUID', 0x19: 'RAW',
             0x1A: 'PEI_DEPEX', 0x1B: 'SMM_DEPEX'}
FFS_TYPES = {0x01: 'SECURITY_CORE', 0x02: 'PEI_CORE', 0x03: 'DXE_CORE',
             0x04: 'PEI_MODULE', 0x05: 'DXE_DRIVER', 0x06: 'DXE_RUNTIME',
             0x07: 'DXE_SAL', 0x08: 'DXE_SMM', 0x09: 'SMM_CORE', 0x0A: 'PEIM',
             0x0B: 'MM_STANDALONE', 0x0C: 'MM_CORE', 0x0D: 'SMM_STANDALONE',
             0x0E: 'APPLICATION', 0x0F: 'FREEFORM', 0xF0: 'FV_IMAGE_PAD'}


def gstr(b):
    d1, d2, d3 = struct.unpack_from("<IHH", b, 0)
    return "%08X-%04X-%04X-%s-%s" % (d1, d2, d3, b[8:10].hex().upper(), b[10:16].hex().upper())


def _raw_lzma(props, body):
    if len(props) < 5 or props[0] >= 225:
        return None
    try:
        filt = [{'id': lzma.FILTER_LZMA1,
                 'dict_size': struct.unpack_from('<I', props, 1)[0] or (1 << 20),
                 'lc': props[0] % 9, 'lp': (props[0] // 9) % 5, 'pb': props[0] // 45}]
        d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt)
        out = d.decompress(body)
        if out and len(out) > 16:
            return out
    except Exception:
        pass
    return None


def lzma_decompress(data, minout=16):
    cands = []
    if len(data) > 32:
        cands.append(('alone', lambda: lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(data)))
        cands.append(('auto', lambda: lzma.decompress(data)))
        cands.append(('edk2-raw', lambda: _raw_lzma(data[4:9], data[9:])))
        cands.append(('props5-raw', lambda: _raw_lzma(data[:5], data[5:])))
        cands.append(('props5-8-raw', lambda: _raw_lzma(data[:5], data[13:])))
        cands.append(('raw-lzma1-16m', lambda: lzma.LZMADecompressor(
            format=lzma.FORMAT_RAW,
            filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': 1 << 24, 'lc': 3, 'lp': 0, 'pb': 2}]
        ).decompress(data)))
    for name, fn in cands:
        try:
            out = fn()
            if out and len(out) >= minout:
                return out, 'lzma-' + name
        except Exception:
            pass
    for skip in (0, 1, 2, 4):
        try:
            out = zlib.decompressobj(-15).decompress(data[skip:])
            if out and len(out) >= minout:
                return out, 'deflate-%d' % skip
        except Exception:
            pass
    return None, None


def efi_tiano(src):
    out = bytearray(); p = 0; bitbuf = 0; bitcnt = 0

    def getbit():
        nonlocal p, bitbuf, bitcnt
        if bitcnt == 0:
            bitbuf = src[p]; p += 1; bitcnt = 8
        b = bitbuf & 1; bitbuf >>= 1; bitcnt -= 1
        return b

    def getbits(n):
        v = 0
        for i in range(n):
            v |= getbit() << i
        return v

    while p < len(src):
        if getbit():
            if getbit():
                n = getbits(4) + 3
                off = getbits(12)
                if off == 0:
                    break
                for _ in range(n):
                    out.append(out[len(out) - off])
            else:
                n = getbits(8) + 1
                for _ in range(n):
                    out.append(src[p]); p += 1
        else:
            out.append(src[p]); p += 1
    return bytes(out)


def efi_decompress(data):
    if len(data) < 8:
        return None, None
    uncomp, algo = struct.unpack_from('<IB', data, 0)
    if algo == 0 and 0 < uncomp <= len(data) - 8:
        return data[8:8+uncomp], 'efi-none'
    if algo == 1:
        try:
            out = efi_tiano(data[8:])
            if out and len(out) > 16:
                return out, 'efi-tiano'
        except Exception:
            pass
    return None, None


class Node:
    __slots__ = ('kind', 'name', 'off', 'size', 'extra', 'children')

    def __init__(self, kind, name, off, size, extra=''):
        self.kind, self.name, self.off, self.size = kind, name, off, size
        self.extra = extra
        self.children = []


def handle_guid_section(d, gd, body_off, body_end, depth, tree, blobs, base, tag):
    raw = d[body_off:body_end]
    label = KNOWN_GUIDS.get(gd, gstr(gd))
    tree.append((depth, Node('guidsec', '[GUID_SEC] ' + label, body_off, len(raw), '')))
    if gd == ACPI_TABLE_GUID:
        blobs.append((tag + '/ACPI_GUIDSEC@0x%X' % (body_off + base), raw, 'acpi'))
    dec, how = lzma_decompress(raw, minout=64)
    if dec is None:
        dec, how = efi_decompress(raw)
    if dec is None:
        tree.append((depth+1, Node('info', '(no decompressor matched)', body_off, len(raw), '')))
        return
    tree.append((depth+1, Node('info', '[>>> DECOMPRESSED %s]' % how, body_off, len(dec), '')))
    blobs.append((tag + '/GUIDDEC@0x%X' % (body_off + base), dec, 'dec'))
    if dec[:4] == b'_FVH' or (len(dec) > 0x40 and dec[0x28:0x2C] == b'_FVH'):
        parse_fv(dec, 0, depth+1, tree, blobs, 0, tag + '/G@0x%X' % body_off)
    else:
        parse_sections(dec, 0, len(dec), depth+1, tree, blobs, 0, tag + '/G@0x%X' % body_off)


def parse_sections(d, start, end, depth, tree, blobs, base, tag=''):
    off = start
    guard = 0
    while off + 4 <= end and guard < 100000:
        guard += 1
        size = d[off] | (d[off+1] << 8) | (d[off+2] << 16)
        st = d[off+3]
        if size == 0xFFFFFF:                     # extended section header
            if off + 28 > end:
                return
            gd = d[off+4:off+20]
            doff, attr = struct.unpack_from('<HH', d, off+20)
            realsize = struct.unpack_from('<I', d, off+24)[0]
            if realsize < 28 or off + realsize > end:
                return
            tree.append((depth, Node('section', '[EXTSEC] ' + SEC_TYPES.get(st, hex(st)),
                                     off, realsize, 'guid=%s doff=0x%X attr=0x%X' % (gstr(gd), doff, attr))))
            if st == 0x17:
                parse_fv(d, off + doff, depth+1, tree, blobs, base, tag)
            elif st == 0x02:
                handle_guid_section(d, gd, off + doff, off + realsize, depth+1, tree, blobs, base, tag)
            off = (off + realsize + 3) & ~3
            continue
        if size < 4 or off + size > end:
            return
        body = d[off+4:off+size]
        stype = SEC_TYPES.get(st, hex(st))
        extra = ''
        if st == 0x01 and len(body) >= 4:
            u, a = struct.unpack_from('<IB', body, 0)
            extra = 'uncomp=0x%X algo=%d' % (u, a)
        elif st == 0x02 and len(body) >= 20:
            gd = body[:16]
            doff, attr = struct.unpack_from('<HH', body, 16)
            extra = 'guid=%s doff=0x%X attr=0x%X' % (gstr(gd), doff, attr)
        elif st == 0x18 and len(body) >= 16:
            extra = 'guid=%s' % gstr(body[:16])
        tree.append((depth, Node('section', stype, off, size, extra)))
        if st == 0x17:
            parse_fv(d, off + 4, depth+1, tree, blobs, base, tag)
        elif st == 0x01:
            dec, how = efi_decompress(body)
            if dec is None:
                dec, how = lzma_decompress(body, minout=64)
            if dec:
                tree.append((depth+1, Node('info', '[>>> DECOMPRESSED %s]' % how, off, len(dec), '')))
                blobs.append((tag + '/CMP@0x%X' % (off + base), dec, 'dec'))
                if dec[0x28:0x2C] == b'_FVH':
                    parse_fv(dec, 0, depth+1, tree, blobs, 0, tag + '/C@0x%X' % off)
                else:
                    parse_sections(dec, 0, len(dec), depth+1, tree, blobs, 0, tag + '/C@0x%X' % off)
        elif st == 0x02:
            gd = body[:16]
            doff, attr = struct.unpack_from('<HH', body, 16)
            if doff < 24:
                doff = 24
            handle_guid_section(d, gd, off + doff, off + size, depth+1, tree, blobs, base, tag)
        off = (off + size + 3) & ~3


def parse_fv(d, start, depth, tree, blobs, base, tag=''):
    if start + 0x40 > len(d) or d[start+0x28:start+0x2C] != b'_FVH':
        return
    fvlen = struct.unpack_from('<Q', d, start+0x20)[0]
    hlen = struct.unpack_from('<H', d, start+0x30)[0]
    extoff = struct.unpack_from('<H', d, start+0x34)[0]
    if fvlen <= 0x38 or start + fvlen > len(d):
        return
    fguid = d[start+0x10:start+0x20]
    fs = 'FFS2' if fguid == FS2 else gstr(fguid)
    tree.append((depth, Node('fv', '[FV] ' + fs, start, fvlen,
                             'len=0x%X hdr=0x%X ext=0x%X' % (fvlen, hlen, extoff))))
    fstart = start + (hlen if hlen >= 0x38 else 0x48)
    if extoff:
        extsize = struct.unpack_from('<I', d, start+extoff+16)[0]
        fstart = (start + extoff + extsize + 7) & ~7
    off = fstart
    endfv = start + fvlen
    while off + 24 <= endfv:
        if d[off:off+24] == b'\xff' * 24:
            tree.append((depth+1, Node('info', '(free space 0x%X)' % (endfv - off), off, 0, '')))
            break
        fg = d[off:off+16]
        ftype = d[off+18]
        fattr = d[off+19]
        fsize = d[off+20] | (d[off+21] << 8) | (d[off+22] << 16)
        state = d[off+23]
        hdrlen = 24
        if fsize < 24 or off + fsize > endfv:
            fsize8 = struct.unpack_from('<Q', d, off+20)[0] & 0xFFFFFFFFFFFF
            if 32 <= fsize8 <= endfv - off:
                fsize = fsize8; hdrlen = 32
            else:
                tree.append((depth+1, Node('info', '!! bad size 0x%X type=%02X @0x%X' % (fsize, ftype, off), off, 0, '')))
                break
        gt = FFS_TYPES.get(ftype, hex(ftype))
        tree.append((depth+1, Node('file', 'F %-15s %s' % (gt, gstr(fg)), off, fsize,
                                   'attr=%02X state=%02X' % (fattr, state))))
        parse_sections(d, off + hdrlen, off + fsize, depth+2, tree, blobs, base, tag)
        off = (off + fsize + 7) & ~7


def find_fvs(d):
    res = []
    n = len(d)
    for o in range(0, n - 0x40, 8):
        if d[o+0x28:o+0x2C] == b'_FVH':
            fvlen = struct.unpack_from('<Q', d, o+0x20)[0]
            if 0x40 < fvlen <= n - o:
                res.append(o)
    return res


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else '.'
    prefix = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(outdir, exist_ok=True)
    d = open(path, 'rb').read()
    print('file %s size=0x%X' % (path, len(d)))
    tree, blobs = [], []
    fvs = find_fvs(d)
    print('candidate FV starts: %d -> %s' % (len(fvs), ['0x%X' % o for o in fvs]))
    for o in fvs:
        parse_fv(d, o, 0, tree, blobs, 0, 'FV@0x%X' % o)
    lines = ['%s%-72s off=0x%-10X size=0x%-9X %s' % ('  '*dep, n.name, n.off, n.size, n.extra)
             for dep, n in tree]
    txt = '\n'.join(lines)
    open(os.path.join(outdir, prefix + '_tree.txt'), 'w', encoding='utf-8').write(txt)
    print('tree lines: %d' % len(lines))
    for i, (label, data, kind) in enumerate(blobs):
        fn = os.path.join(outdir, '%s_blob%02d_%s.bin' % (prefix, i, kind))
        open(fn, 'wb').write(data)
        print('blob %02d %-44s %10d  %s' % (i, label, len(data), fn))
    print()
    print(txt[:15000])


main()
