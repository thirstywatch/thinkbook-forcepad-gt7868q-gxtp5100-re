# -*- coding: utf-8 -*-
"""追查两个工具里的高熵块是什么，以及工具本身的用途。只读文件。"""
import io, os, math, re

CANDS = [
    ('goodix-fw-tool', r'<LAB>\touchpad-lab\poc\pkg\goodix-fw-tool.exe',
     [(0x7C3000, 0x7DE000), (0x7E5000, 0x7F9000)]),
    ('Dell_Hellcat', r'<LAB>\touchpad-lab\poc\pkg\extract\zip0\DellTouchpadUpdate_Hellcat_v0.2.2.100.exe',
     [(0x04C000, 0x060000)]),
]

out = []
def P(s=''):
    print(s); out.append(str(s))

def ent(b):
    if not b: return 0.0
    c = [0] * 256
    for x in b: c[x] += 1
    e = 0.0
    for v in c:
        if v:
            p = v / len(b); e -= p * math.log2(p)
    return e

MARKS = [b'BERLIN', b'YELSTO', b'7936', b'7868', b'GOODIXTOUCHPADCAPSULE', b'Goodix',
         b'PK\x03\x04', b'MSCF', b'7z\xbc\xaf\x27\x1c', b'UPX!', b'gtx8', b'\x1f\x8b\x08']

for name, path, blobs in CANDS:
    d = open(path, 'rb').read()
    P('=' * 78)
    P('### %s' % name)
    P('=' * 78)

    P('  --- 打包器 / 运行时指纹 ---')
    for m in [b'go1.', b'rustc', b'Go build ID:', b'UPX!', b'Inno Setup', b'Nullsoft',
              b'7-Zip', b'MSCF', b'PK\x03\x04', b'Wise', b'InstallShield', b'bzlib',
              b'lzma', b'zstd', b'__COMPACT', b'.rsrc']:
        i = d.find(m)
        if i >= 0:
            P('    %-14s @ %s' % (m.decode('latin1'), hex(i)))
    P()

    P('  --- "payload" 出现处的上下文（判断工具用途）---')
    n = 0
    for m in (b'payload', b'Payload', b'PAYLOAD'):
        i = d.find(m)
        while i >= 0 and n < 6:
            a = max(0, i - 60); b = min(len(d), i + 80)
            seg = d[a:b]
            txt = ''.join(chr(x) if 32 <= x < 127 else '.' for x in seg)
            P('    @%s : %s' % (hex(i), txt))
            n += 1
            i = d.find(m, i + 1)
    P()

    for (a, b) in blobs:
        blob = d[a:b]
        P('  --- 高熵块 0x%06X..0x%06X (%d B, 熵 %.3f) ---' % (a, b, len(blob), ent(blob[:262144])))
        P('    首 64 B: %s' % blob[:64].hex(' '))
        P('    ASCII  : %s' % ''.join(chr(x) if 32 <= x < 127 else '.' for x in blob[:64]))
        # gtx8 假设：u32be = firmware_size，且 size+6 ≈ 块长
        for off in range(0, 64, 4):
            v = int.from_bytes(blob[off:off + 4], 'big')
            if abs((v + 6) - len(blob)) < 4096:
                P('    ★ 偏移 %d 处 u32be=%d，+6=%d ≈ 块长 %d ⇒ 疑似 gtx8 firmware_size'
                  % (off, v, v + 6, len(blob)))
        hits = []
        for m in MARKS:
            i = blob.find(m)
            if i >= 0:
                hits.append('%s@%s' % (m.decode('latin1', 'replace').replace('\x1f', 'GZ').replace('\xbc', ''), hex(i)))
        P('    块内标记: %s' % (hits if hits else '（无）'))
        # 熵剖面（64KB 步）
        prof = []
        for k in range(0, min(len(blob), 262144), 65536):
            prof.append('0x%X:%.2f' % (k, ent(blob[k:k + 4096])))
        P('    熵剖面(64KB步): %s' % '  '.join(prof))
        P()

o = r'<LAB>\touchpad-lab\re\tool_blob_probe_out.txt'
io.open(o, 'w', encoding='utf-8').write('\n'.join(out))
print('[已写] ' + o)
