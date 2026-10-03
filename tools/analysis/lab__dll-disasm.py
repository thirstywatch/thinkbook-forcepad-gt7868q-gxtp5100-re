# -*- coding: utf-8 -*-
"""反汇编 tpupdate_driver.dll 的指定函数（按 RVA），并把 LEA 目标注解成字符串/数据。
   用法: dll-disasm.py <dll> <hexRVA> [maxInsn]
"""
import struct, re, sys, os
from capstone import *

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

def rva2off(pe, rva):
    for s in pe['secs']:
        if s['va'] <= rva < s['va'] + max(s['vsz'], s['rsz']):
            return s['raw'] + (rva - s['va'])
    return None

def funcs(pe, d):
    out = []
    for s in pe['secs']:
        if s['name'] != '.pdata':
            continue
        buf = d[s['raw']:s['raw'] + s['rsz']]
        for i in range(0, len(buf) - 11, 12):
            a, b, u = struct.unpack_from('<III', buf, i)
            if a and b and 0 < b - a < 0x8000:
                out.append((a, b))
    return sorted(out)

def main(path, rva, maxn=400):
    d = open(path, 'rb').read()
    pe = parse_pe(d)
    ib = pe['ib']
    F = funcs(pe, d)
    cands = [(a, b) for a, b in F if a <= rva < b]
    if not cands:
        print("RVA 0x%X 不在任何 .pdata 函数里；从它开始反汇编到下一个函数起点" % rva)
        nxt = min([a for a, b in F if a > rva], default=rva + 0x400)
        a, b = rva, nxt
    else:
        a, b = min(cands, key=lambda t: t[1] - t[0])
    print("### function RVA 0x%06X - 0x%06X  (%d B)  file 0x%06X" % (a, b, b - a, rva2off(pe, a) or 0))

    # 数据注解表：LEA 目标 -> 可读串
    def data_str(rva):
        o = rva2off(pe, rva)
        if o is None:
            return None
        s = d[o:o + 200]
        m = re.match(rb'[\x20-\x7e]{4,}', s)
        if m:
            return repr(m.group().decode('latin1')[:120])
        return None

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    off = rva2off(pe, a)
    end = rva2off(pe, b)
    code = d[off:end]
    n = 0
    for ins in md.disasm(code, a):
        # 自己按字节解 RIP 相对（capstone 的 detail 在部分环境里不稳）
        raw = code[ins.address - a: ins.address - a + 10]
        ann = ""
        for k in range(0, min(4, len(raw) - 6)):
            kk = k
            if raw[kk] in (0x48, 0x4C):
                kk += 1
            if kk + 1 < len(raw) and raw[kk] in (0x8D, 0x8B) and (raw[kk + 1] & 0xC7) == 0x05:
                disp = struct.unpack_from('<i', raw, kk + 2)[0]
                tgt = ins.address + kk + 2 + 4 + disp
                ds = data_str(tgt)
                ann = "   ; 0x%X%s" % (tgt, (" = " + ds) if ds else "")
                break
        print("0x%06X  %-34s%s" % (ins.address, ins.mnemonic + " " + ins.op_str, ann))
        n += 1
        if n >= maxn:
            print("... (truncated)")
            break

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 400)
