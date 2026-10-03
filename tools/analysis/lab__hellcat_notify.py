# hellcat_notify.py - 反汇编 NotifyICEnterUpdate 调用写函数前后的参数构造
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

def dump(va, n, tag):
    f = va2f(va)
    if f is None or f+n > len(data):
        print('  (范围无效)'); return
    print('\n=== %s @0x%08X ===' % (tag, va))
    for ins in md.disasm(data[f:f+n], va):
        print('   0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))

# NotifyICEnterUpdate 里 0x40DF54 调用写函数之前的代码
dump(0x40DDE0, 0x180, 'NotifyICEnterUpdate（写函数调用点之前）')

# 找出所有调用写函数 0x411560 的位置（找 raw mode / 关上报 / 各种写）
print('\n=== 调用 0x411560（写内存）的所有位置 ===')
hits = []
for off in range(len(data)-5):
    if data[off] == 0xE8:
        src = f2va(off)
        if src is None: continue
        rel = struct.unpack_from('<i', data, off+1)[0]
        if src + 5 + rel == 0x411560:
            hits.append(src)
print('  %d 处: %s' % (len(hits), ', '.join('0x%X' % h for h in hits[:20])))

# 找调用读函数 0x4113b0 的位置
print('\n=== 调用 0x4113b0（读内存）的位置 ===')
hits2 = []
for off in range(len(data)-5):
    if data[off] == 0xE8:
        src = f2va(off)
        if src is None: continue
        rel = struct.unpack_from('<i', data, off+1)[0]
        if src + 5 + rel == 0x4113b0:
            hits2.append(src)
print('  %d 处: %s' % (len(hits2), ', '.join('0x%X' % h for h in hits2[:20])))
