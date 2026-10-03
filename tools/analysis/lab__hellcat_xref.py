# hellcat_xref.py - 解析 PE，反查关键字符串的交叉引用，dump 出命令构造代码
import struct, re, capstone

P = r'<LAB>\touchpad-lab\vendor\dup\DellTouchpadUpdate_Hellcat_v0.2.2.100.exe'
data = open(P, 'rb').read()

# ---- PE 解析 ----
e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
assert data[e_lfanew:e_lfanew+4] == b'PE\x00\x00'
coff = e_lfanew + 4
nsec = struct.unpack_from('<H', data, coff+2)[0]
optsz = struct.unpack_from('<H', data, coff+16)[0]
opt = coff + 20
magic = struct.unpack_from('<H', data, opt)[0]
image_base = struct.unpack_from('<I', data, opt+28)[0] if magic == 0x10b else struct.unpack_from('<Q', data, opt+24)[0]
print('PE magic=0x%X  段数=%d  ImageBase=0x%X' % (magic, nsec, image_base))
secs = []
so = opt + optsz
for i in range(nsec):
    name = data[so+i*40:so+i*40+8].rstrip(b'\x00').decode('latin-1')
    vsz, va, rsz, rp = struct.unpack_from('<IIII', data, so+i*40+8)
    secs.append((name, va, vsz, rp, rsz))
    print('  %-8s VA=0x%06X VSize=0x%06X RawPtr=0x%06X RawSize=0x%06X' % (name, va, vsz, rp, rsz))

def f2va(off):
    for (n, va, vsz, rp, rsz) in secs:
        if rp <= off < rp + rsz:
            return image_base + va + (off - rp)
    return None

def va2f(va):
    rva = va - image_base
    for (n, sva, vsz, rp, rsz) in secs:
        if sva <= rva < sva + vsz:
            return rp + (rva - sva)
    return None

TARGETS = [
    (0x041F00, 'switch to raw data mode failed'),
    (0x041E4C, 'GetRawDataStatus read from 4100'),
    (0x041E8C, 'GetRawDataStatus get 0x80'),
    (0x041FD0, 'switch to raw normal mode failed'),
]

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

for (off, tag) in TARGETS:
    va = f2va(off)
    print('\n=========== 字符串 "%s"  VA=0x%X ===========' % (tag, va))
    pat = struct.pack('<I', va)
    hits = []
    i = data.find(pat)
    while i >= 0 and len(hits) < 8:
        hits.append(i)
        i = data.find(pat, i+1)
    print('  引用 %d 处: %s' % (len(hits), ', '.join('0x%X' % h for h in hits)))
    for h in hits[:3]:
        start = max(0, h - 0xA0)
        print('  --- 代码上下文 (file 0x%X) ---' % start)
        for ins in md.disasm(data[start:start+0x140], f2va(start)):
            mark = '  <<<' if h <= (start + (ins.address - f2va(start))) < h+4 else ''
            print('     0x%08X  %-8s %s%s' % (ins.address, ins.mnemonic, ins.op_str, mark))
