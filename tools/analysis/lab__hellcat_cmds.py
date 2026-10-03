# hellcat_cmds.py - 从 Hellcat 工具里挖出完整命令表（含 raw data mode 切换命令）
import re, struct

P = r'<LAB>\touchpad-lab\vendor\dup\DellTouchpadUpdate_Hellcat_v0.2.2.100.exe'
data = open(P, 'rb').read()
print('大小 %d' % len(data))

def dump(off, n=64, tag=''):
    print('\n--- %s @0x%X ---' % (tag, off))
    for i in range(0, n, 16):
        chunk = data[off+i:off+i+16]
        print('   %04X  %-47s  %s' % (i, ' '.join('%02X' % b for b in chunk),
              ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)))

# 已定位的关键位置
for (off, tag) in [(0x44480, 'reset/load-flash 命令区'),
                   (0x107D0, 'I2C_DIRECT_RW 使用区'),
                   (0x3BAE0, '0x60DC 引用区'),
                   (0x17020, '0x452C 引用区'),
                   (0x1850,  '0xC000 引用区(1)')]:
    dump(off, 80, tag)

# 搜所有"命令形状"的 6 字节序列：xx xx 00 00 01 01
print('\n=== 形如 ?? ?? 00 00 01 01 的命令序列 ===')
pat = re.compile(rb'..\x00\x00\x01\x01', re.S)
seen = {}
for m in pat.finditer(data):
    s = m.group(0)
    key = s.hex()
    seen.setdefault(key, []).append(m.start())
for k, offs in sorted(seen.items(), key=lambda kv: -len(kv[1]))[:25]:
    print('   %s   命中 %d 处  首个@0x%X  %s' % (' '.join(k[i:i+2] for i in range(0, 12, 2)),
          len(offs), offs[0], ('ASCII: ' + repr(bytes.fromhex(k))) if all(32 <= b < 127 for b in bytes.fromhex(k)) else ''))

# 搜 "raw" 相关字符串及位置
print('\n=== raw / mode 相关字符串 ===')
for m in re.finditer(rb'[\x20-\x7E]{4,}', data):
    s = m.group(0).decode('latin-1')
    if re.search(r'raw|Raw|mode|Mode', s) and len(s) < 90:
        print('   @0x%06X  %s' % (m.start(), s))
