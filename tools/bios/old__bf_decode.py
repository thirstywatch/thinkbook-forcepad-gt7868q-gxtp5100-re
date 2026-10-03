#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Brute-force LZMA/DEFLATE decode attempts over candidate GUID_DEFINED sections."""
import struct, sys, lzma, zlib

LZMA_GUID = bytes.fromhex("9858ee4e14395942d69ede7bd79403cf")


def try_all(data, maxskip=128, verbose=False):
    hits = []
    n = len(data)
    for skip in range(0, min(maxskip, n - 20)):
        blob = data[skip:]
        # A) EDK2 LZMA guided section: u32 uncomp + 5 props + raw stream
        if len(blob) > 13:
            props = blob[4:9]
            body = blob[9:]
            try:
                filt = [{'id': lzma.FILTER_LZMA1,
                         'dict_size': struct.unpack_from('<I', props, 1)[0] or (1 << 20),
                         'lc': props[0] % 9, 'lp': (props[0] // 9) % 5, 'pb': props[0] // 45}]
                out = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt).decompress(body)
                if out and len(out) > 256:
                    hits.append((skip, 'edk2-uncomp+props', len(out), out[:64]))
            except Exception:
                pass
        # B) 5 props + raw stream (no size field)
        for hdr in (5, 13):
            if len(blob) <= hdr + 5: continue
            props = blob[:5]
            if props[0] >= 225: continue
            try:
                filt = [{'id': lzma.FILTER_LZMA1,
                         'dict_size': struct.unpack_from('<I', props, 1)[0] or (1 << 20),
                         'lc': props[0] % 9, 'lp': (props[0] // 9) % 5, 'pb': props[0] // 45}]
                out = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt).decompress(blob[hdr:])
                if out and len(out) > 256:
                    hits.append((skip, 'props%d+raw' % hdr, len(out), out[:64]))
            except Exception:
                pass
        # C) .lzma alone (13-byte header)
        try:
            out = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(blob)
            if out and len(out) > 256:
                hits.append((skip, 'alone', len(out), out[:64]))
        except Exception:
            pass
        # D) xz / auto
        try:
            out = lzma.decompress(blob)
            if out and len(out) > 256:
                hits.append((skip, 'auto', len(out), out[:64]))
        except Exception:
            pass
        # E) raw deflate
        for so in (0, 1, 2):
            try:
                out = zlib.decompressobj(-15).decompress(blob[so:])
                if out and len(out) > 256:
                    hits.append((skip, 'deflate+%d' % so, len(out), out[:64]))
            except Exception:
                pass
    return hits


if __name__ == '__main__':
    path = sys.argv[1]
    d = open(path, 'rb').read()
    regions = []
    for a in sys.argv[2:]:
        lo, hi = a.split('-')
        regions.append((int(lo, 0), int(hi, 0)))
    for lo, hi in regions:
        data = d[lo:hi]
        print('=== region 0x%X-0x%X (%d bytes) ===' % (lo, hi, len(data)))
        hits = try_all(data)
        seen = set()
        for skip, how, ln, head in hits:
            k = (how, ln)
            print('  skip=%-4d %-18s out=%9d head=%s' % (skip, how, ln, head[:32].hex()))
