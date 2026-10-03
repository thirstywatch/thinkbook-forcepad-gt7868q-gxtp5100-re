# -*- coding: utf-8 -*-
"""MSVC RTTI 走查：类名 -> type_info -> Complete Object Locator -> vtable -> 虚函数槽
   用法: dll-rtti.py <dll> [类名子串...]
"""
import struct, re, sys, os

def parse_pe(d):
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    optsz = struct.unpack_from('<H', d, pe + 20)[0]
    opt = pe + 24
    pe32p = (struct.unpack_from('<H', d, opt)[0] == 0x20b)
    ib = struct.unpack_from('<Q' if pe32p else '<I', d, opt + (24 if pe32p else 28))[0]
    secs = []
    so = opt + optsz
    for i in range(nsec):
        e = so + i * 40
        name = d[e:e + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, ra = struct.unpack_from('<IIII', d, e + 8)
        secs.append(dict(name=name, va=va, vsz=vsz, raw=ra, rsz=rsz))
    return dict(ib=ib, secs=secs)

def off2rva(pe, off):
    for s in pe['secs']:
        if s['raw'] <= off < s['raw'] + s['rsz']:
            return s['va'] + (off - s['raw'])
    return None

def rva2off(pe, rva):
    for s in pe['secs']:
        if s['va'] <= rva < s['va'] + max(s['vsz'], s['rsz']):
            return s['raw'] + (rva - s['va'])
    return None

def main(path, wants):
    d = open(path, 'rb').read()
    pe = parse_pe(d)
    ib = pe['ib']
    print("### %s (%d B base=0x%X)" % (os.path.basename(os.path.dirname(path)), len(d), ib))

    # 1) 收集所有 .?AV 名
    names = {}
    for m in re.finditer(rb'\.\?A[VU][\x20-\x7e]{2,80}', d):
        rva = off2rva(pe, m.start())
        if rva:
            names[m.group().decode('latin1')] = rva

    # 2) 找 type_info：vftbl(8) + _M_data(8) + name_ptr(8)  => 指向 name 的 8 字节 VA 出现在 name-16 处
    tinfo = {}   # class -> type_info RVA
    for nm, nrva in names.items():
        pat = struct.pack('<Q', nrva + ib)
        for m in re.finditer(re.escape(pat), d):
            trva = off2rva(pe, m.start())
            if trva and trva > 16:
                cand = trva - 16      # type_info 起点
                tinfo.setdefault(nm, []).append(cand)

    # 3) COL：signature(4)=1, offset(4), cdOffset(4), pTypeDescriptor(4 RVA), pClassDesc(4 RVA), pSelf(4 RVA)
    cols = {}
    for nm, cands in tinfo.items():
        for trva in cands:
            pat = struct.pack('<I', trva)
            for m in re.finditer(re.escape(pat), d):
                orva = off2rva(pe, m.start())
                if orva is None or orva < 12:
                    continue
                crou = orva - 12
                off = rva2off(pe, crou)
                if off is None:
                    continue
                sig = struct.unpack_from('<I', d, off)[0]
                if sig != 1:
                    continue
                pself = struct.unpack_from('<I', d, off + 20)[0]
                if pself != crou:
                    continue
                cols.setdefault(nm, []).append(crou)

    # 4) vtable：u32@(vt-8) == COL
    print()
    for nm in sorted(wants):
        cls = [k for k in names if nm in k]
        print("=== %s  ->  %s" % (nm, cls))
        for c in cls:
            for crou in cols.get(c, []):
                pat = struct.pack('<I', crou)
                vts = []
                for m in re.finditer(re.escape(pat), d):
                    orva = off2rva(pe, m.start())
                    if orva:
                        vts.append(orva + 4)
                print("   COL rva=0x%06X  vtable @ %s" % (crou, [hex(v) for v in vts]))
                for vt in vts:
                    off = rva2off(pe, vt)
                    if off is None:
                        continue
                    for i in range(16):
                        fn = struct.unpack_from('<Q', d, off + i * 8)[0]
                        frva = fn - ib if fn > ib else fn
                        print("      [%2d] 0x%016X -> rva 0x%06X" % (i, fn, frva))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or ["CfgImage", "TlcConnection", "FwImage"])
