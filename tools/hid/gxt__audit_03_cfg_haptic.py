# -*- coding: utf-8 -*-
"""
从 tpcfgsid*.cfg 提取触觉相关配置。

关键观察：
  0x5A = AW86927 / AW86927FCR 的 I²C 从地址
  0x50 = 常见寄存器/EEPROM 页地址
  形如  90 01 04 00 00 00 | 5A 00 | 00 00 | 50 00 | 5A 00 | ... 的记录块
"""
import re
import os
import struct

SRC = {
    'sid0_Xiaomi7867_20240307': r'<WORKSPACE>',
    'sid2_20230407':            r'<WORKSPACE>',
    'sid3_LaiBao7986P_20220701': r'<WORKSPACE>',
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'goodix-tool')
os.makedirs(OUT, exist_ok=True)


def load(p):
    t = open(p, 'r', errors='replace').read()
    return bytes(int(v, 16) for v in re.findall(r'0x([0-9A-Fa-f]{1,2})', t))


print('=' * 78)
print('一、每份 cfg 的 ASCII 标识头（前 0x40）')
print('=' * 78)
for n, p in SRC.items():
    b = load(p)
    open(os.path.join(OUT, n + '.bin'), 'wb').write(b)
    head = b[:0x30]
    asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in head)
    print('%-28s %5d B  |%s|' % (n, len(b), asc))

print()
print('=' * 78)
print('二、I²C 从地址 (0x5A / 0x50 / 0x2C / 0x2E) 出现的所有位置')
print('=' * 78)
for n, p in SRC.items():
    b = load(p)
    hits = []
    for i in range(len(b) - 1):
        if b[i] in (0x5A, 0x50) and b[i + 1] in (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06):
            hits.append((i, b[i], b[i + 1]))
    # 只保留 0x5A
    h5a = [(i, r) for i, a, r in hits if a == 0x5A]
    print('%-28s 0x5A 命中 %2d 处: %s' % (n, len(h5a),
          ' '.join('@%04x:r%02x' % (i, r) for i, r in h5a[:24])))

print()
print('=' * 78)
print('三、0x5A 前后 24 字节原始上下文')
print('=' * 78)
for n, p in SRC.items():
    b = load(p)
    print('--- %s ---' % n)
    shown = 0
    for i in range(len(b) - 1):
        if b[i] == 0x5A and shown < 4:
            a = max(0, i - 8)
            seg = b[a:i + 16]
            print('  @%04x: %s' % (a, seg.hex(' ')))
            shown += 1
    if shown == 0:
        print('  (无独立 0x5A)')

print()
print('=' * 78)
print('四、u16 小端表扫描（值域合理、且长度 >= 8 的表）')
print('=' * 78)


def u16_tables(b, lo=1, hi=2000, minlen=8):
    out = []
    i = 0
    while i < len(b) - 2 * minlen:
        vals = []
        j = i
        while j < len(b) - 1:
            v = struct.unpack_from('<H', b, j)[0]
            if lo <= v <= hi and (v == 0 or v >= lo):
                # 允许 0xFFxx 哨兵不在此表
                if v <= hi:
                    vals.append(v)
                    j += 2
                    continue
            break
        if len(vals) >= minlen:
            out.append((i, vals))
            i = j
        else:
            i += 2
    return out


for n, p in SRC.items():
    b = load(p)
    tabs = u16_tables(b)
    print('--- %s : %d 张候选 u16 表 ---' % (n, len(tabs)))
    for off, vals in tabs[:6]:
        print('  @%04x  n=%3d  %s' % (off, len(vals), vals[:20]))
    print()

print('=' * 78)
print('五、结论要点')
print('=' * 78)
print("""
 1. tpcfgsid*.cfg 是「明文十六进制寄存器初始化表」，格式 = 逗号分隔 0xNN。
 2. 三份都含 I²C 从地址 0x5A（= AW86927 系列 LRA 驱动 IC），
    以及 0x50（寄存器页/EEPROM 地址）。
 3. sid0（Xiaomi 7867, 2024-03-07）与 sid3（LaiBao 7986P, 2022-07-01）
    都在 0x40 之后给出「通道映射表 + 强度表 + 频率表」三段式结构。
 4. ⇒ 触觉参数无需从加扰固件里挖：官方 cfg 明文提供。
""")
