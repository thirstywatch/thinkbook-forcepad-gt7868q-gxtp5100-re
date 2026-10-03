# d2_cpd.py —— 探查 Lenovo/Insyde "$CPD" 组件容器（BIOS 镜像分区）
# 用法: python d2_cpd.py <image.bin> <part_name> <off_hex> <size_hex>
import sys, struct, re, math, zlib

path, name, off, size = sys.argv[1], sys.argv[2], int(sys.argv[3], 16), int(sys.argv[4], 16)
d = open(path, 'rb').read()
seg = d[off:off + size]
print('=== 分区 %s  偏移 0x%X  大小 0x%X (%d B) ===' % (name, off, size, len(seg)))

print('\n--- 头 256 字节 ---')
for o in range(0, 256, 16):
    h = ' '.join('%02X' % x for x in seg[o:o + 16])
    a = ''.join(chr(x) if 32 <= x < 127 else '.' for x in seg[o:o + 16])
    print(' %04X  %-47s  %s' % (o, h, a))

# 熵（分块）
def ent(b):
    if not b: return 0.0
    c = [0] * 256
    for x in b: c[x] += 1
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c if v)
print('\n--- 熵（每 4KB 块，仅打印与整体差异大的前 12 块） ---')
blocks = [(i, ent(seg[i:i + 4096])) for i in range(0, len(seg), 4096)]
print('  整体熵 %.3f  块数 %d' % (ent(seg), len(blocks)))
low = sorted(blocks, key=lambda t: t[1])[:12]
for i, e in low:
    print('   低熵块 @0x%06X  熵 %.3f' % (i, e))

# 压缩/容器签名
print('\n--- 签名扫描 ---')
sigs = {
    b'\x24\x43\x50\x44': '$CPD', b'_FVH': 'FVH', b'PE\x00\x00': 'PE',
    b'\x5D\x00\x00\x80': 'LZMA(5D 00 00 80)', b'\x5D\x00\x00': 'LZMA(5D 00 00)',
    b'\x28\xB5\x2F\xFD': 'ZSTD', b'\x1F\x8B\x08': 'GZIP', b'PK\x03\x04': 'ZIP',
    b'\xAA\x55': 'AA55', b'EFI\x00': 'EFI_PART', b'\x0C\xF0\x00': '?',
}
for s, nm in sigs.items():
    offs = [m.start() for m in re.finditer(re.escape(s), seg)]
    if offs:
        print('  %-16s %4d 次  前几处: %s' % (nm, len(offs), [hex(x) for x in offs[:8]]))

# 字符串
print('\n--- 关键字符串（ASCII / UTF-16LE） ---')
for k in ['GXTP', 'Goodix', 'GOODIX', 'TB14P', 'b6ae105a', '7868', 'Firmware', 'TouchPad',
          'Touchpad', 'TPAD', 'I2C', 'HID', 'Haptic', 'Vib', 'Pei', 'Dxe', 'Setup']:
    for enc, tag in ((k.encode(), 'A'), (k.encode('utf-16-le'), 'U')):
        offs = [m.start() for m in re.finditer(re.escape(enc), seg)]
        if offs:
            print('  %-10s [%s] %3d 次  前几处: %s' % (k, tag, len(offs), [hex(x) for x in offs[:5]]))
