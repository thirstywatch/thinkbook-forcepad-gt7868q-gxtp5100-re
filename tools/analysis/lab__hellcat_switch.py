# hellcat_switch.py - 反汇编 0x411560（疑似 raw data mode 切换）及其调用链
import struct, capstone

P = r'<LAB>\touchpad-lab\vendor\dup\DellTouchpadUpdate_Hellcat_v0.2.2.100.exe'
data = open(P, 'rb').read()
e = struct.unpack_from('<I', data, 0x3C)[0]
coff = e + 4
nsec = struct.unpack_from('<H', data, coff+2)[0]
optsz = struct.unpack_from('<H', data, coff+16)[0]
opt = coff + 20
image_base = struct.unpack_from('<I', data, opt+28)[0]
secs = []
so = opt + optsz
for i in range(nsec):
    name = data[so+i*40:so+i*40+8].rstrip(b'\x00').decode('latin-1')
    vsz, va, rsz, rp = struct.unpack_from('<IIII', data, so+i*40+8)
    secs.append((name, va, vsz, rp, rsz))
def va2f(va):
    rva = va - image_base
    for (n, sva, vsz, rp, rsz) in secs:
        if sva <= rva < sva + vsz:
            return rp + (rva - sva)
    return None
def f2va(off):
    for (n, va, vsz, rp, rsz) in secs:
        if rp <= off < rp + rsz:
            return image_base + va + (off - rp)
    return None

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

def dump(va, n=0x120, tag=''):
    f = va2f(va)
    print('\n=== %s  @0x%08X (file 0x%X) ===' % (tag, va, f))
    for ins in md.disasm(data[f:f+n], va):
        print('   0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))

dump(0x411560, 0x140, '疑似 raw-mode 切换函数')
dump(0x4113b0, 0x100, '0x4100 读函数')

# 找 0x411560 的调用者
print('\n=== 调用 0x411560 的位置 ===')
target = struct.pack('<I', 0x411560)
hits = []
i = data.find(b'\xE8')   # call rel32
# 简单扫描：所有 E8 后 4 字节的目标等于 0x411560
for off in range(len(data)-5):
    if data[off] == 0xE8:
        src = f2va(off)
        if src is None: continue
        rel = struct.unpack_from('<i', data, off+1)[0]
        if src + 5 + rel == 0x411560:
            hits.append(src)
print('  %s' % (', '.join('0x%X' % h for h in hits[:10]) or '无'))
for h in hits[:2]:
    dump(h-0x60, 0x120, '调用者上下文 @0x%X' % h)
