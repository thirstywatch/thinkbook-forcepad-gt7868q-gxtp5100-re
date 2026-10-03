# -*- coding: utf-8 -*-
"""定位某个日志串的 LEA 引用点并反汇编其前后代码（找相邻的立即数/常量）"""
import struct, re, sys
from capstone import *

D = open(r"<WORKSPACE>", 'rb').read()
IB = 0x180000000
SECS = [('.text', 0x1000, 0x400, 49152), ('PAGE', 0xD000, 0xC400, 1536),
        ('.rdata', 0xE000, 0xCA00, 37376), ('.data', 0x17000, 0x14E00, 1024)]

def o2r(o):
    for n, v, r, s in SECS:
        if r <= o < r + s:
            return v + o - r
def r2o(r):
    for n, v, r, s in SECS:
        if v <= r < v + s:
            return r + r - v

def parse_pe(d):
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    optsz = struct.unpack_from('<H', d, pe + 20)[0]
    so = pe + 24 + optsz
    out = []
    for i in range(nsec):
        e = so + i * 40
        name = d[e:e + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, ra = struct.unpack_from('<IIII', d, e + 8)
        out.append((name, va, ra, rsz))
    return out
PE = parse_pe(D)
def O2R(o):
    for n, v, r, s in PE:
        if r <= o < r + s:
            return v + o - r
def R2O(r):
    for n, v, r, s in PE:
        if v <= r < v + max(s, 0x1000):
            return r + r - v

def disasm(a, lo, hi):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    off = R2O(a)
    end = R2O(hi)
    for ins in md.disasm(D[off:end], a):
        raw = D[R2O(ins.address):R2O(ins.address) + 10]
        ann = ""
        for k in range(0, min(4, len(raw) - 6)):
            kk = k
            if raw[kk] in (0x48, 0x4C): kk += 1
            if kk + 1 < len(raw) and raw[kk] in (0x8D, 0x8B) and (raw[kk + 1] & 0xC7) == 0x05:
                dp = struct.unpack_from('<i', raw, kk + 2)[0]
                t = ins.address + kk + 2 + 4 + dp
                oo = R2O(t)
                s = re.match(rb'[\x20-\x7e]{4,}', D[oo:oo + 90]) if oo else None
                ann = "  ;0x%X%s" % (t, (" = " + s.group().decode('latin1')[:70]) if s else "")
                break
        print("     0x%06X  %-34s%s" % (ins.address, ins.mnemonic + " " + ins.op_str, ann))

for pat in [b"Write cfg data to 0x", b"send cfg cmd i:", b"Write send cfg finish cmd",
            b"Chip write cfg finish cmd is sucess", b"Download cfg successfully",
            b"Chip write cfg cmd is ready"]:
    m = re.search(re.escape(pat) + rb'[\x20-\x7e]{0,90}', D)
    if not m:
        print("not found:", pat); continue
    rva = O2R(m.start())
    print("=" * 90)
    print("### %r  @ rva 0x%X" % (pat.decode(), rva))
    for n, v, r, s in PE:
        if n not in ('.text', 'PAGE'):
            continue
        buf = D[r:r + s]
        for i in range(len(buf) - 10):
            j = i
            if buf[j] in (0x48, 0x4C): j += 1
            if buf[j] == 0x8D and (buf[j + 1] & 0xC7) == 0x05:
                dp = struct.unpack_from('<i', buf, j + 2)[0]
                t = v + i + (j - i) + 2 + 4 + dp
                if rva - 8 <= t <= rva:
                    site = v + i
                    print("   site = 0x%X" % site)
                    disasm(max(site - 150, 0x1000), site - 150, site + 70)
                    print()
