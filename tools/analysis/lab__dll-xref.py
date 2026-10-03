# -*- coding: utf-8 -*-
"""DLL 字符串引用覆盖度诊断：所有 [Info]/[Error] 日志串，到底有没有代码引用它们？
   试三种寻址形式：LEA r64,[rip+d] / MOV r64,[rip+d] / MOV r64, imm64
   目的：定位 CfgImage::load 的代码位置（或证明这层逻辑不在本模块）。"""
import struct, re, sys, os, collections

SECT = None

def parse_pe(d):
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    mach, nsec = struct.unpack_from('<HH', d, pe + 4)
    # COFF header: Machine(2) NSections(2) TimeDate(4) PtrSymTab(4) NSym(4) SizeOfOptHdr(2) Characteristics(2)
    optsz = struct.unpack_from('<H', d, pe + 4 + 16)[0]
    opt = pe + 24
    magic = struct.unpack_from('<H', d, opt)[0]
    pe32p = (magic == 0x20b)
    ib = struct.unpack_from('<Q' if pe32p else '<I', d, opt + (24 if pe32p else 28))[0]
    secs = []
    so = opt + optsz
    for i in range(nsec):
        e = so + i * 40
        name = d[e:e + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, ra = struct.unpack_from('<IIII', d, e + 8)
        secs.append(dict(name=name, va=va, vsz=vsz, raw=ra, rsz=rsz))
    return dict(ib=ib, secs=secs, pe32p=pe32p)

def off2rva(pe, off):
    for s in pe['secs']:
        if s['raw'] <= off < s['raw'] + s['rsz']:
            return s['va'] + (off - s['raw'])
    return None

def main(path):
    d = open(path, 'rb').read()
    pe = parse_pe(d)
    print("=" * 96)
    print("### %s  (%d B, base=0x%X)" % (os.path.basename(path), len(d), pe['ib']))
    for s in pe['secs']:
        print("   %-8s va=0x%06X vsz=%-7d raw=0x%06X rsz=%d" %
              (s['name'], s['va'], s['vsz'], s['raw'], s['rsz']))

    # 1) 收集日志串及其 RVA
    #    ★ 坑：日志串在 .rdata 里带【前导缩进空格】（Debug=3、Info/Error/Warning=4），
    #      所以代码里的 LEA 指向的是 "[...." 往前 3~5 字节处，不是 '['。
    strs = []
    for m in re.finditer(rb'\[(?:Info|Error|Debug|Warning|Trace)\][\x20-\x7e]{6,}', d):
        rva = off2rva(pe, m.start())
        if rva:
            strs.append((rva, m.start(), m.group().decode('latin1')))
    print("   日志串 %d 条" % len(strs))
    tgt = {}
    for rva, off, s in strs:
        # '[' 与真实串起点（往前吃空格）
        k = 0
        while off - 1 - k >= 0 and d[off - 1 - k] == 0x20:
            k += 1
        for j in range(0, max(k, 4) + 1):
            r2 = rva - j
            if r2 > 0:
                tgt.setdefault(r2, []).append(s)

    # 2) 扫代码节
    code = [s for s in pe['secs'] if s['name'] in ('.text', 'PAGE')]
    leahit = collections.Counter(); movhit = collections.Counter(); immhit = collections.Counter()
    all_lea = 0
    for s in code:
        buf = d[s['raw']:s['raw'] + s['rsz']]
        n = len(buf)
        for i in range(n - 10):
            # LEA r64,[rip+d]
            j = i
            if buf[j] in (0x48, 0x4C): j += 1
            if j + 6 <= n and buf[j] == 0x8D and (buf[j + 1] & 0xC7) == 0x05:
                disp = struct.unpack_from('<i', buf, j + 2)[0]
                t = s['va'] + i + (j - i) + 2 + 4 + disp
                all_lea += 1
                if t in tgt: leahit[t] += 1
            # MOV r64,[rip+d]
            j = i
            if buf[j] in (0x48, 0x4C): j += 1
            if j + 6 <= n and buf[j] == 0x8B and (buf[j + 1] & 0xC7) == 0x05:
                disp = struct.unpack_from('<i', buf, j + 2)[0]
                t = s['va'] + i + (j - i) + 2 + 4 + disp
                if t in tgt: movhit[t] += 1
            # MOV r64, imm64  (REX.W + B8+r)
            if buf[i] in (0x48, 0x4C) and 0xB8 <= buf[i + 1] <= 0xBF:
                imm = struct.unpack_from('<Q', buf, i + 2)[0]
                t = imm - pe['ib']
                if t in tgt: immhit[t] += 1
    print("   LEA(rip) 总数 %d ; 命中日志串的 %d 条串" % (all_lea, len(leahit)))
    print("   MOV(rip) 命中 %d ; MOV imm64 命中 %d" % (len(movhit), len(immhit)))
    got = set(leahit) | set(movhit) | set(immhit)
    gotstr = set()
    for t in got: gotstr.update(tgt.get(t, []))
    print("   ⇒ 被引用的日志串 %d / %d" % (len(got), len(strs)))
    miss = [r for r in strs if r[2] not in gotstr]
    print("   ⇒ 未被引用 %d 条；抽样前 12 条：" % len(miss))
    for rva, off, s in miss[:12]:
        print("      rva=0x%06X  %s" % (rva, s[:88]))
    hit = [r for r in strs if r[2] in gotstr]
    print("   ⇒ 已引用抽样前 6 条：")
    for rva, off, s in hit[:6]:
        print("      rva=0x%06X  (lea x%d mov x%d imm x%d)  %s" %
              (rva, leahit[rva], movhit[rva], immhit[rva], s[:70]))
    return pe, d

for p in sys.argv[1:]:
    main(p)
