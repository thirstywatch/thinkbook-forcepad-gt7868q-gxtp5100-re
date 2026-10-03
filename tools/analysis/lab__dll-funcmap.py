# -*- coding: utf-8 -*-
"""用 .pdata 枚举函数边界 + 把日志串 LEA 归类到函数，定位 CfgImage::load 等目标函数"""
import struct, re, sys, os, collections
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

def funcs(pe, d):
    pd = [s for s in pe['secs'] if s['name'] == '.pdata']
    out = []
    for s in pd:
        buf = d[s['raw']:s['raw'] + s['rsz']]
        for i in range(0, len(buf) - 11, 12):
            a, b, u = struct.unpack_from('<III', buf, i)
            if a and b and b > a:
                out.append((a, b, u))
    return sorted(out)

def main(path, needles):
    d = open(path, 'rb').read()
    pe = parse_pe(d)
    ib = pe['ib']
    F = funcs(pe, d)
    print("### %s  %d B  base=0x%X  函数 %d 个 (.pdata)" % (os.path.basename(os.path.dirname(path)), len(d), ib, len(F)))

    # 收集 LEA -> 目标（含 '[' 前 5 字节窗口）
    leas = collections.defaultdict(list)
    for s in pe['secs']:
        if s['name'] not in ('.text', 'PAGE'):
            continue
        buf = d[s['raw']:s['raw'] + s['rsz']]
        for i in range(len(buf) - 10):
            j = i
            if buf[j] in (0x48, 0x4C): j += 1
            if buf[j] == 0x8D and (buf[j + 1] & 0xC7) == 0x05:
                disp = struct.unpack_from('<i', buf, j + 2)[0]
                t = s['va'] + i + (j - i) + 2 + 4 + disp
                leas[t].append(s['va'] + i)

    # 串 -> 引用点
    strsite = {}
    for m in re.finditer(rb'\[(?:Info|Error|Debug|Warning|Trace)\][\x20-\x7e]{6,}', d):
        rva = off2rva(pe, m.start())
        if rva is None:
            continue
        k = 0
        while m.start() - 1 - k >= 0 and d[m.start() - 1 - k] == 0x20:
            k += 1
        sites = []
        for j in range(0, max(k, 5) + 1):
            sites += leas.get(rva - j, [])
        strsite[m.group().decode('latin1')] = sites

    def fn_of(rva):
        for a, b, u in F:
            if a <= rva < b:
                return a
        return None

    groups = collections.defaultdict(list)
    for s, sites in strsite.items():
        for site in sites:
            f = fn_of(site)
            if f is not None:
                groups[f].append(s)

    # 找含 needls 的函数
    for nd in needles:
        print()
        print("=== needle: %r ===" % nd)
        got = 0
        for f, ss in sorted(groups.items()):
            if any(nd in x for x in ss):
                got += 1
                print("  函数 RVA 0x%06X (file 0x%06X)  含 %d 条相关串" %
                      (f, r2o if False else (rva2off(pe, f) or 0), len(ss)))
                for x in ss[:8]:
                    print("      ", x[:96])
        if not got:
            print("   未找到")

if __name__ == "__main__":
    needles = ["CfgImage::load", "cfgUpdateWithFile", "Write cfg data to", "CfgImage::load> Cfg file error"]
    for p in sys.argv[1:]:
        main(p, needles)
