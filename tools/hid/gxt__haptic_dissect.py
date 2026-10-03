# -*- coding: utf-8 -*-
"""
A-14 攻坚：解剖 sid0 @0x0336 (TAG=0x0E, LEN=89) 和 sid3 @0x0460 (TAG=0x12, LEN=81)

这两个块是唯二「同时含 400ms 与 600ms」或「同时含 300/400/500/1000」的块，
是振动参数块的最强候选。

方法：多视图对照
  V1 逐个 u16 打印，标注落在时长常量表里的项
  V2 按 u8 打印
  V3 与另外两份 cfg 的同 TAG 块做并排对齐
  V4 尝试「子结构切分」：看能否切成 {u16 数, u16 数, ...} 的重复组
"""
import os, struct, json
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(HERE, 'cfg')
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)

FILES = ['sid0.bin', 'sid2.bin', 'sid3.bin']
BEST = {'sid0.bin': 0x38, 'sid2.bin': 0x40, 'sid3.bin': 0x40}

KNOWN = {0x0190: '400', 0x0258: '600', 0x03E8: '1000', 0x012C: '300', 0x01F4: '500',
         0x0064: '100', 0x00C8: '200', 0x001E: '30', 0x0032: '50', 0x0014: '20',
         0x000A: '10', 0x0060: '96', 0x00FA: '250', 0x0080: '128', 0x0002: '2',
         0x0001: '1', 0x0003: '3', 0x0004: '4', 0x0005: '5', 0x000A: '10'}

L = []
def w(s=''):
    L.append(s)
    print(s)


def walk_keep(data, start):
    keep, i, n = [], start, len(data)
    while i < n:
        if i + 2 > n:
            break
        tag, ln = data[i], data[i + 1]
        j = i + 2 + ln
        if j > n:
            break
        if not (tag == 0 and ln == 0):
            keep.append((i, tag, ln, data[i + 2:j]))
        i = j
    return keep


def dump_u16_view(p, name):
    w('**%s —— u16 视图**' % name)
    w()
    w('```')
    u = [struct.unpack_from('<H', p, k)[0] for k in range(0, len(p) - 1, 2)]
    for row in range(0, len(u), 4):
        cells = []
        for k in range(row, min(row + 4, len(u))):
            mark = ''
            if u[k] in KNOWN:
                mark = '<%s>' % KNOWN[u[k]]
            cells.append('%5d%s' % (u[k], mark))
        w('  +%3d: %s' % (row * 2, '  '.join(cells)))
    w('```')
    w()


def dump_u8_view(p, name):
    w('**%s —— u8 视图**' % name)
    w()
    w('```')
    for row in range(0, len(p), 16):
        chunk = p[row:row + 16]
        hexs = ' '.join('%02x' % x for x in chunk)
        txt = ''.join(chr(x) if 32 <= x < 127 else '.' for x in chunk)
        w('  +%3d: %-47s |%s|' % (row, hexs, txt))
    w('```')
    w()


def try_substructure(p, name):
    """尝试切成 3-u16 组 / 4-u16 组，看重复度"""
    w('**%s —— 子结构试探**' % name)
    w()
    u = [struct.unpack_from('<H', p, k)[0] for k in range(0, len(p) - 1, 2)]
    for stride in (2, 3, 4, 5, 6):
        if len(u) < stride * 2:
            continue
        groups = [tuple(u[k:k + stride]) for k in range(0, len(u) - stride + 1, stride)]
        c = Counter(groups)
        rep = c.most_common(3)
        # 只看「成组长度能整除」
        if len(u) % stride:
            note = '（不整除，余 %d）' % (len(u) % stride)
        else:
            note = '（整除）'
        w('  - 步长 %d：%d 组，最常见 %s %s'
          % (stride, len(groups),
             ', '.join(str(x) for x in rep), note))
    w()


def main():
    w('=' * 78)
    w('A-14 振动参数块解剖')
    w('=' * 78)

    dat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(HERE, fn)
        dat[fn] = open(p, 'rb').read()

    keep = {fn: walk_keep(dat[fn], BEST[fn]) for fn in FILES}

    targets = [('sid0.bin', 0x0336), ('sid3.bin', 0x0460), ('sid0.bin', 0x003A),
               ('sid0.bin', 0x0253), ('sid3.bin', 0x069D)]

    for fn, off in targets:
        blk = [(o, t, l, p) for (o, t, l, p) in keep[fn] if o == off]
        if not blk:
            w('!! %s @0x%04X 未找到' % (fn, off))
            continue
        _, t, l, p = blk[0]
        w()
        w('---')
        w('## %s @0x%04X  TAG=`0x%02X`  LEN=%d' % (fn, off, t, l))
        w()
        dump_u16_view(p, 'u16')
        dump_u8_view(p, 'u8')
        if l >= 40:
            try_substructure(p, '子结构')

    # ---------- 并排对齐：0x0E 与 0x12 ----------
    w()
    w('---')
    w('## 跨文件并排：同类块的对齐检查')
    w()
    for fn in FILES:
        for (o, t, l, p) in keep[fn]:
            if l < 40:
                continue
            # 只打印含 >=2 个时长常量的
            u = [struct.unpack_from('<H', p, k)[0] for k in range(0, len(p) - 1, 2)]
            nk = sum(1 for x in u if x in KNOWN)
            if nk >= 8:
                w('- %s @0x%04X TAG=`0x%02X` LEN=%d —— 含 %d 个已知常量' % (fn, o, t, l, nk))

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'haptic_blocks_dissect.txt'), 'w', encoding='utf-8').write(txt)
    w()
    w('写入：cfg_parsed/haptic_blocks_dissect.txt')


main()
