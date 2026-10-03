# -*- coding: utf-8 -*-
"""迷你 PE 工具：解析节表 + 在 .text 里找指向 .rdata 字符串的 RIP 相对引用
   用法: python pefind.py <exe/dll> "<字符串子串>"  [--ctx N]
"""
import sys, struct, re

def parse_pe(d):
    if d[:2] != b'MZ': raise SystemExit('not PE')
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    assert d[pe:pe+4] == b'PE\0\0', 'no PE sig'
    coff = pe + 4
    mach, nsec = struct.unpack_from('<HH', d, coff)
    optsz = struct.unpack_from('<H', d, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from('<H', d, opt)[0]
    pe32p = (magic == 0x20b)
    imagebase = struct.unpack_from('<Q' if pe32p else '<I', d, opt + (24 if pe32p else 28))[0]
    secs = []
    so = opt + optsz
    for i in range(nsec):
        e = so + i * 40
        name = d[e:e+8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, ra = struct.unpack_from('<IIII', d, e + 8)
        secs.append(dict(name=name, va=va, vsz=vsz, raw=ra, rsz=rsz))
    return dict(imagebase=imagebase, secs=secs, pe32p=pe32p, mach=mach)

def rva2off(pe, rva):
    for s in pe['secs']:
        if s['va'] <= rva < s['va'] + max(s['vsz'], s['rsz']):
            return s['raw'] + (rva - s['va'])
    return None

def off2rva(pe, off):
    for s in pe['secs']:
        if s['raw'] <= off < s['raw'] + s['rsz']:
            return s['va'] + (off - s['raw'])
    return None

def main():
    path = sys.argv[1]
    needle = sys.argv[2].encode()
    d = open(path, 'rb').read()
    pe = parse_pe(d)
    print('machine=0x%04X (%s)  imagebase=0x%X  sections=%d'
          % (pe['mach'], {0x8664: 'x64', 0x14c: 'x86', 0xaa64: 'arm64'}.get(pe['mach'], '?'),
             pe['imagebase'], len(pe['secs'])))
    for s in pe['secs']:
        print('  %-8s va=0x%08X vsz=%-8d raw=0x%06X rsz=%d' % (s['name'], s['va'], s['vsz'], s['raw'], s['rsz']))

    hits = [m.start() for m in re.finditer(re.escape(needle), d)]
    print('\n字符串命中 %d 处' % len(hits))
    targets = set()
    for h in hits[:8]:
        rva = off2rva(pe, h)
        print('  file 0x%06X  rva 0x%08X  va 0x%X  %r' % (h, rva or 0, (rva or 0) + pe['imagebase'],
              d[h:h+len(needle)+40]))
        if rva: targets.add(rva)

    print('\n在 .text 里找 RIP 相对引用（lea/mov reg,[rip+d]）…')
    found = []
    for s in pe['secs']:
        if not s['name'].startswith('.text'): continue
        buf = d[s['raw']:s['raw'] + s['rsz']]
        for i in range(len(buf) - 7):
            # 48/4C 8D modrm(mod=00,rm=101)  →  lea r64, [rip+disp32]
            if buf[i] in (0x48, 0x4C) and buf[i+1] == 0x8D and (buf[i+2] & 0xC7) == 0x05:
                disp = struct.unpack_from('<i', buf, i + 3)[0]
                tgt = (s['va'] + i + 7 + disp)
                if tgt in targets:
                    found.append((s['raw'] + i, s['va'] + i, tgt,
                                  buf[i:i+7].hex(' ')))
            # 8B (mov r64, [rip+d]) 少用，跳过
    print('  引用点 %d 个' % len(found))
    for foff, frva, tgt, by in found[:20]:
        print('  file 0x%06X  rva 0x%08X  -> 0x%X   bytes %s' % (foff, frva, tgt, by))
    if found:
        with open('_xref.txt', 'w', encoding='utf-8') as f:
            for foff, frva, tgt, by in found:
                f.write('%06X %08X %X %s\n' % (foff, frva, tgt, by))
        print('  ⇒ 写入 _xref.txt')

main()
