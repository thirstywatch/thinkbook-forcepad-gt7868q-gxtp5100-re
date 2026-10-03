import collections, math, struct

a = open('NJME01WW.exe', 'rb').read()[0x2C000:]
b = open('NJME07WW.exe', 'rb').read()[0x2C000:]

print('overlay 长度 A=%d  B=%d' % (len(a), len(b)))
n = min(len(a), len(b))
same = sum(1 for i in range(n) if a[i] == b[i])
print('两版逐字节相同率 = %.2f%%  (%d/%d)' % (same * 100.0 / n, same, n))
print('  随机基线 = 0.391%')

print('\n前 24 字节对齐比较:')
for i in range(24):
    print('  %02X  A=%02X %s B=%02X' % (i, a[i], '  ' if a[i] == b[i] else '≠ ', b[i]))


def H(x):
    c = collections.Counter(x)
    m = len(x)
    return -sum(v / m * math.log2(v / m) for v in c.values())


print('\n熵: A=%.3f  B=%.3f  （8.0=加密/随机, ~6=压缩, <5=明文）'
      % (H(a[:200000]), H(b[:200000])))

for name, d in (('A', a), ('B', b)):
    c = collections.Counter(d[:200000])
    print('\n%s overlay 最常见 8 字节:' % name)
    for v, k in c.most_common(8):
        print('   0x%02X  %.2f%%' % (v, k * 100.0 / 200000))

# 尾部结构
print('\nA 末32B:', a[-32:].hex(' '))
print('B 末 32B:', b[-32:].hex(' '))
# 在 A 里搜 LZMA 的 5D 00 00 80 00 (props=0x5D dict=8MB) 这类常见头
print('\n搜 LZMA 常见头 (5D 00 / 5D 00 00 xx xx xx) 在 A 中的位置:')
for i in range(0, min(len(a) - 5, 400000)):
    if a[i] == 0x5D and a[i + 1] == 0x00 and (a[i + 2] & 0x1F) == 0 and a[i + 2] != 0:
        ds = struct.unpack_from('<I', a, i + 1)[0]
        if 1 < ds <= 1 << 24 and (ds & (ds - 1)) == 0:
            print('   @0x%06X props=0x5D dict=%u (2^%d)' % (i, ds, ds.bit_length() - 1))
            if i > 8:
                break