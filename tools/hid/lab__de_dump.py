# de_dump.py —— 反汇编 32/64 位 PE 的指定 VA 区间
# 用法: python de_dump.py <exe> <va_hex> <len_hex> [va_hex len_hex ...]
import struct, sys
from capstone import *

path = sys.argv[1]
b = open(path, 'rb').read()
pe = struct.unpack('<I', b[0x3C:0x40])[0]
nsec = struct.unpack('<H', b[pe + 6:pe + 8])[0]
optsz = struct.unpack('<H', b[pe + 20:pe + 22])[0]
magic = struct.unpack('<H', b[pe + 24:pe + 26])[0]
is64 = magic == 0x20B
image_base = struct.unpack('<Q' if is64 else '<I',
                           b[pe + 48:pe + 56] if is64 else b[pe + 52:pe + 56])[0]
sectab = pe + 24 + optsz
secs = []
for i in range(nsec):
    o = sectab + 40 * i
    nm = b[o:o + 8].rstrip(b'\x00').decode('latin1')
    vs, va, rs, ro = struct.unpack('<IIII', b[o + 8:o + 24])
    secs.append((nm, va, vs, ro, rs))

def va2off(va):
    for nm, sva, vsz, ro, rs in secs:
        base = image_base + sva
        if base <= va < base + max(vsz, rs):
            d = ro + (va - base)
            return d if 0 <= d < len(b) else None
    return None

md = Cs(CS_ARCH_X86, CS_MODE_64 if is64 else CS_MODE_32)
print('ImageBase 0x%X  %s' % (image_base, 'x64' if is64 else 'x86'))
for i in range(2, len(sys.argv), 2):
    va = int(sys.argv[i], 16)
    ln = int(sys.argv[i + 1], 16)
    off = va2off(va)
    print('\n===== VA 0x%X len 0x%X (file 0x%X) =====' % (va, ln, off or 0))
    if off is None:
        print('  (VA 不在任何节里)')
        continue
    for ins in md.disasm(b[off:off + ln], va):
        line = '  %08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str)
        # 标注立即数里的报告 ID / 关键常量
        print(line)
