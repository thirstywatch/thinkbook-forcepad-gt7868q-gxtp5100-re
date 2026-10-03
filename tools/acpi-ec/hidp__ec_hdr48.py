#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ec_hdr48.py -- 解析 48 字节定长头。

已确认的事实：
  · overlay 前 48 字节在两版间【逐字节完全相同】
  · offset 48 起两版完全分叉（逐字节差异率回到 0.39% 随机基线）
  · overlay 末尾两版都是 00 00 00 00 00 00 00（七连零）
  ⇒ 形态 = [48 B 定长头][变长 payload][尾部零填充]

⇒ 头里极可能含：magic / 版本 / 原始长度 / 校验 / 压缩参数
⇒ 找"哪几个u32 等于一个合理的 payload 长度"，就能定出边界并拿到已知明文。
"""
import struct

a = open('NJME01WW.exe', 'rb').read()[0x2C000:]
b = open('NJME07WW.exe', 'rb').read()[0x2C000:]
H = 48

print('=' * 92)
print('48 字节头逐字段解读（LE 与 BE 各试）')
print('=' * 92)
print('  raw:', a[:H].hex(' '))
print()
for base, tag in ((a, 'A'), (b, 'B')):
    print('  --- %s ---' % tag)
    for i in range(0, H, 4):
        le = struct.unpack_from('<I', base, i)[0]
        be = struct.unpack_from('>I', base, i)[0]
        print('    +%02d  LE32=%-12d(0x%08X)   BE32=%-12d(0x%08X)'
              % (i, le, le, be, be))
    print()

print('=' * 92)
print('★ 找"看起来像长度/大小"的字段（两版应当接近各自 payload 长度）')
print('=' * 92)
ovA, ovB = len(a), len(b)
print('  overlay 长度: A=%d  B=%d' % (ovA, ovB))
print()
for i in range(0, H - 3, 4):
    leA = struct.unpack_from('<I', a, i)[0]
    leB = struct.unpack_from('<I', b, i)[0]
    beA = struct.unpack_from('>I', a, i)[0]
    beB = struct.unpack_from('>I', b, i)[0]
    for nm, vA, vB, endo in (('LE', leA, leB, '<'), ('BE', beA, beB, '>')):
        if 0x1000 < vA < 0x400000 and 0x1000 < vB < 0x400000:
            # 若是长度，应该和 overlay 长度同量级
            rA = vA / ovA
            if 0.3 < rA < 1.05:
                print('    +%02d %s: A=%-10d (%.3f×overlay)  B=%-10d (%.3f×overlay)  ★ 可能是长度'
                      % (i, nm, vA, rA, vB, vB / ovB))
            else:
                print('    +%02d %s: A=%-10d (%.3f×)  B=%-10d (%.3f×)'
                      % (i, nm, vA, rA, vB, vB / ovB))

print()
print('=' * 92)
print('★ 找 LZMA props（常见 0x5D = lc3/lp0/pb2）出现的位置')
print('=' * 92)
for i in range(0, 64):
    if a[i] in (0x5D, 0x5C, 0x5E, 0x2D, 0x00):
        nxt = a[i + 1:i + 5]
        d = struct.unpack_from('<I', nxt)[0] if len(nxt) == 4 else 0
        pow2 = (d and (d & (d - 1)) == 0)
        print('  off %2d: 0x%02X  后 4B=%s  LE32=%-10d %s'
              % (i, a[i], nxt.hex(' ') if nxt else '', d,
                 '★是2的幂⇒合法 dictsize' if pow2 else ''))
