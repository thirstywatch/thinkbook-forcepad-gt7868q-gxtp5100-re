#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List / extract files from a FAT12/16/32 volume embedded in a file."""
import struct, sys, os

class Fat:
    def __init__(self, path, base, size=None):
        self.f = open(path, 'rb')
        self.base = base
        self.f.seek(base); self.b = self.f.read(512)
        self.bps = struct.unpack_from('<H', self.b, 11)[0]
        self.spc = self.b[13]
        self.rsvd = struct.unpack_from('<H', self.b, 14)[0]
        self.nfats = self.b[16]
        self.rootsz = struct.unpack_from('<H', self.b, 17)[0]
        self.tot16 = struct.unpack_from('<H', self.b, 19)[0]
        self.media = self.b[21]
        self.fatsz16 = struct.unpack_from('<H', self.b, 22)[0]
        self.spt = struct.unpack_from('<H', self.b, 24)[0]
        self.heads = struct.unpack_from('<H', self.b, 26)[0]
        self.tot32 = struct.unpack_from('<I', self.b, 32)[0]
        self.fatsz32 = struct.unpack_from('<I', self.b, 36)[0]
        self.rootclus = struct.unpack_from('<I', self.b, 44)[0]
        self.fatsz = self.fatsz32 or self.fatsz16
        self.tot = self.tot32 or self.tot16
        self.cluster_bytes = self.bps * self.spc
        self.root_off = base + (self.rsvd + self.nfats * self.fatsz) * self.bps
        self.data_off = self.root_off + self.rootsz * 32
        self.data_sectors = self.tot - (self.rsvd + self.nfats * self.fatsz + self.rootsz * 32 // self.bps)
        self.nclusters = self.data_sectors // self.spc
        if self.nclusters < 4085: self.type = 12
        elif self.nclusters < 65525: self.type = 16
        else: self.type = 32
        # load first FAT
        self.f.seek(base + self.rsvd * self.bps)
        self.fat = self.f.read(self.fatsz * self.bps)

    def fat_entry(self, n):
        if self.type == 12:
            off = n + n // 2
            v = struct.unpack_from('<H', self.fat, off)[0]
            return (v & 0xFFF) if (n & 1) == 0 else (v >> 4)
        if self.type == 16:
            return struct.unpack_from('<H', self.fat, n*2)[0]
        return struct.unpack_from('<I', self.fat, n*4)[0] & 0x0FFFFFFF

    def is_eoc(self, v):
        if self.type == 12: return v >= 0xFF8
        if self.type == 16: return v >= 0xFFF8
        return v >= 0x0FFFFFF8

    def cluster_off(self, c):
        return self.data_off + (c - 2) * self.cluster_bytes

    def chain(self, c, limit=2_000_000):
        out = []
        seen = set()
        while 2 <= c < self.nclusters + 2 and not self.is_eoc(c) and c not in seen and len(out) < limit:
            seen.add(c); out.append(c); c = self.fat_entry(c)
        return out

    def read_chain(self, c):
        self.f.seek(self.cluster_off(c)) if False else None
        buf = bytearray()
        for cc in self.chain(c):
            self.f.seek(self.cluster_off(cc))
            buf += self.f.read(self.cluster_bytes)
        return bytes(buf)

    def read_rootdir(self):
        if self.type == 32:
            return self.read_chain(self.rootclus)
        self.f.seek(self.root_off)
        return self.f.read(self.rootsz * 32)

    def entries(self, rawdir):
        out = []
        lfn = []
        p = 0
        while p + 32 <= len(rawdir):
            e = rawdir[p:p+32]; p += 32
            if e[0] == 0x00: break
            if e[0] == 0xE5: lfn = []; continue
            attr = e[11]
            if attr == 0x0F:
                seq = e[0]
                chunk = e[1:11] + e[14:26] + e[28:32]
                try:
                    s = chunk.decode('utf-16-le', 'ignore')
                except Exception:
                    s = ''
                s = s.split('\x00')[0]
                lfn.insert(0, s)
                continue
            name = e[0:8].decode('latin1').rstrip(' ')
            ext = e[8:11].decode('latin1').rstrip(' ')
            short = name + ('.' + ext if ext else '')
            long_name = ''.join(lfn) if lfn else None
            lfn = []
            if name in ('.', '..') or (attr & 0x08):
                continue
            clus = (struct.unpack_from('<H', e, 20)[0] << 16) | struct.unpack_from('<H', e, 26)[0]
            size = struct.unpack_from('<I', e, 28)[0]
            out.append(dict(short=short, long=long_name, attr=attr,
                            isdir=bool(attr & 0x10), cluster=clus, size=size))
        return out

    def walk(self, rawdir=None, prefix='', depth=0, out=None):
        if out is None: out = []
        if rawdir is None: rawdir = self.read_rootdir()
        for e in self.entries(rawdir):
            disp = (e['long'] or e['short'])
            out.append((prefix + disp, e))
            if e['isdir'] and depth < 12:
                sub = self.read_chain(e['cluster']) if e['cluster'] >= 2 else b''
                if sub:
                    self.walk(sub, prefix + disp + '/', depth + 1, out)
        return out


if __name__ == '__main__':
    path = sys.argv[1]; base = int(sys.argv[2], 0)
    fa = Fat(path, base)
    print('bps=%d spc=%d nfats=%d fatsz=%d tot=%d type=FAT%d nclusters=%d' % (
        fa.bps, fa.spc, fa.nfats, fa.fatsz, fa.tot, fa.type, fa.nclusters))
    print('root_off=0x%X data_off=0x%X' % (fa.root_off, fa.data_off))
    ents = fa.walk()
    for name, e in ents:
        print('%-58s %-12s clus=%-8d size=%-10d off=0x%X' % (
            name, 'DIR' if e['isdir'] else '', e['cluster'], e['size'],
            fa.cluster_off(e['cluster']) if e['cluster'] >= 2 else 0))
    if len(sys.argv) > 3:
        outdir = sys.argv[3]
        os.makedirs(outdir, exist_ok=True)
        for name, e in ents:
            if e['isdir']: continue
            data = fa.read_chain(e['cluster'])[:e['size']] if e['cluster'] >= 2 else b''
            safe = name.replace('/', '_').replace('\\', '_')
            op = os.path.join(outdir, safe)
            open(op, 'wb').write(data)
            print('wrote', op, len(data))
