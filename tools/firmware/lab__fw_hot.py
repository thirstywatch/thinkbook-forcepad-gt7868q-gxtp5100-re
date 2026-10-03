# fw_hot.py — 反汇编可疑的报文分派区，并解出 tbb 跳转表目标
import struct, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = False

def foff(a):
    return VOFF + (a - BASE)

def dis(start, length, tag=''):
    print('\n=== 反汇编 0x%08X..0x%08X %s ===' % (start, start + length, tag))
    for ins in md.disasm(data[foff(start):foff(start) + length], start):
        print('  0x%08X  %-10s %s' % (ins.address, ins.mnemonic, ins.op_str))

# 主战场
dis(0x0800B300, 0x100, '(cmp #14 + tbb 附近)')

# 解 tbb 跳转表
for A in (0x0800B3D6, 0x0800B5C6, 0x0800B896, 0x0800B920, 0x0800B96A):
    off = foff(A)
    op = data[off:off+4]
    print('\n=== 跳转表 @0x%08X  (%s) 原始字节: %s ===' % (A, op.hex(), data[off:off+24].hex()))
    pc = A + 4
    if op[1] == 0xE8:      # tbh: 半字偏移
        for i in range(8):
            v = struct.unpack_from('<H', data, off + 4 + i*2)[0]
            print('   case %d -> 0x%08X' % (i, pc + 2*v))
    else:                  # tbb: 字节偏移
        for i in range(12):
            v = data[off + 4 + i]
            print('   case %d -> 0x%08X' % (i, pc + 2*v))
