# -*- coding: utf-8 -*-
"""
A-13 突破：识别出**嵌套块**语法 —— 魔数 0x5C30 / 0x5416 / 0x550A 等。

观察（来自 haptic_dissect）：
  sid0 @0x0336 TAG=0x0E payload 尾部：
      ... 00 00 | 30 5c | 0a 00 14 00 50 00 20 03 e8 03 d0 07 40 1f 10 27 | 58 02 2d 00 90 01 | 00 00 | 88 13 00 00 10 27 00 00 f4
                ^^^^^   ^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                subTAG  ?     一串 u16 常量
  sid0 @0x003A TAG=0x00 payload 尾部：
      ... 00 00 | 0c 5d | 06 00 | 00 00 ...
      ... 00 00 | 16 5f | 00 04 | ...
  sid3 @0x0460 TAG=0x12 payload 尾部：
      ... 00 00 | 06 53 | 3e 00 | 00 00
      ... 00 00 | 0a 55 | 28 00 3c 00 | 01 00 00 00 2a

假设 H：存在**二级魔数**，形如 `u16 LE`，高字节在 0x50–0x5F 之间（'P'..'_'），
       第二字节低 7 位是某种序号。即 `30 5c` = 0x5C30，`16 5f`=0x5F16，`0a 55`=0x550A。
       这些魔数之后跟 `u16 计数` + `u16 × 计数` 的数据数组。

检验：
  Q1 全 cfg 扫描：u16 落在 0x5000–0x5FFF 的位置有多少？它们的分布如何？
  Q2 每个这样的位置，其后的 u16 是否「像计数」（值域合理、且后面真的跟那么多个 u16）？
  Q3 这些二级块是否能完整覆盖 payload 的尾部（即构成一个嵌套 TLV 流）？
"""
import os, struct, json
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(HERE, 'cfg')
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)

FILES = ['sid0.bin', 'sid2.bin', 'sid3.bin']
BEST = {'sid0.bin': 0x38, 'sid2.bin': 0x40, 'sid3.bin': 0x40}

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


def main():
    w('=' * 78)
    w('A-13 突破：二级魔数（嵌套块）识别')
    w('=' * 78)

    dat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(HERE, fn)
        dat[fn] = open(p, 'rb').read()

    keep = {fn: walk_keep(dat[fn], BEST[fn]) for fn in FILES}

    # ---------- Q1 全文件扫描二级魔数 ----------
    w()
    w('### Q1 二级魔数扫描：u16 ∈ [0x5000,0x5FFF] 的全部位点')
    w()
    w('| 文件 | 偏移 | u16 | 高/低字节 | 后续 u16（4 个） | 后续 u8（12 个） |')
    w('|---|---|---|---|---|---|')
    hits = defaultdict(list)
    for fn in FILES:
        data = dat[fn]
        for k in range(0, len(data) - 1):
            v = struct.unpack_from('<H', data, k)[0]
            if 0x5000 <= v <= 0x5FFF:
                nxt = [struct.unpack_from('<H', data, k + 2 + 2 * i)[0]
                       for i in range(4) if k + 2 + 2 * i + 1 < len(data)]
                raw = data[k + 2:k + 14]
                hits[v].append((fn, k))
                w('| %s | 0x%04X | `0x%04X` | %02X/%02X | %s | `%s` |'
                  % (fn, k, v, data[k + 1], data[k], nxt, raw.hex(' ')))
    w()
    w('**二级魔数汇总**：')
    for v in sorted(hits):
        fs = Counter(f for f, _ in hits[v])
        w('- `0x%04X` × %d · %s' % (v, len(hits[v]),
                                     ', '.join('%s@0x%04X' % (f[:4], k) for f, k in hits[v][:8])))

    # ---------- Q2 二级块解析：魔数后是否跟计数+数组 ----------
    w()
    w('### Q2 二级块解析试探：`[u16 magic][u16 count][u16 × count]`')
    w()
    w('| 文件 | 魔数位置 | magic | count候选 | count×2+4 是否落在块/文件边界 | 数组前 8 项 |')
    w('|---|---|---|---|---|---|')
    for v in sorted(hits):
        for (fn, k) in hits[v]:
            data = dat[fn]
            if k + 4 > len(data):
                continue
            cnt = struct.unpack_from('<H', data, k + 2)[0]
            need = 4 + 2 * cnt
            end = k + need
            # 数组
            arr = [struct.unpack_from('<H', data, k + 4 + 2 * i)[0]
                   for i in range(min(cnt, 8)) if k + 4 + 2 * i + 1 < len(data)]
            # 找一个「最近的块边界」
            nb = min((abs((o + 2 + l) - end), o + 2 + l)
                     for (o, t, l, p) in keep[fn] if o + 2 + l >= end) \
                if any(o + 2 + l >= end for (o, t, l, p) in keep[fn]) else (None, None)
            w('| %s | 0x%04X | `0x%04X` | %d | %s (最近块尾 0x%04X) | %s |'
              % (fn, k, v, cnt,
                 '✅ 命中' if nb[0] is not None and nb[0] <= 8 else ('~%s' % nb[0]),
                 nb[1] or 0, arr))

    # ---------- Q3 二级块在整个 payload 里的分布 ----------
    w()
    w('### Q3 含二级魔数的「一级块」是哪些')
    w()
    w('| 文件 | 一级块偏移 | 一级 TAG | 一级 LEN | 块内魔数 | 魔数相对位置 |')
    w('|---|---|---|---|---|---|')
    for fn in FILES:
        for (o, t, l, p) in keep[fn]:
            found = []
            for k in range(0, len(p) - 1):
                v = struct.unpack_from('<H', p, k)[0]
                if 0x5000 <= v <= 0x5FFF:
                    found.append((k, v))
            if found:
                w('| %s | 0x%04X | `0x%02X` | %d | %s | %s |'
                  % (fn, o, t, l,
                     ', '.join('`0x%04X`' % v for _, v in found),
                     ', '.join('+%d' % k for k, _ in found)))

    # ---------- Q4 sid0 @0x0336 的完整二级解析 ----------
    w()
    w('### Q4 🔬 全解剖 sid0 @0x0336 (TAG=0x0E, LEN=89)')
    w()
    data = dat['sid0.bin']
    p = data[0x336 + 2:0x336 + 2 + 89]
    w('原始 hex：')
    w('```')
    for r in range(0, len(p), 16):
        w('  +%3d: %s' % (r, p[r:r + 16].hex(' ')))
    w('```')
    w()
    w('按「u16 序列 + 魔数标注」逐项：')
    w()
    w('| 偏移 | u16 | 备注 |')
    w('|---|---|---|')
    NAMES = {0x0190: '400ms', 0x0258: '600ms', 0x03E8: '1000', 0x012C: '300',
             0x01F4: '500', 0x0064: '100', 0x00C8: '200', 0x001E: '30',
             0x0032: '50', 0x0014: '20', 0x000A: '10', 0x0060: '96',
             0x00FA: '250', 0x0080: '128', 0x2710: '10000', 0x1388: '5000',
             0x1F40: '8000', 0x07D0: '2000', 0x0320: '800'}
    for k in range(0, len(p) - 1, 2):
        u = struct.unpack_from('<H', p, k)[0]
        note = ''
        if u in NAMES:
            note = '★ 常量 %s' % NAMES[u]
        if 0x5000 <= u <= 0x5FFF:
            note = '🔑 二级魔数'
        w('| +%d | %d (`0x%04X`) | %s |' % (k, u, u, note))

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'nested_magic.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'magics': {'%04X' % v: [[f, k] for f, k in s] for v, s in hits.items()}},
              open(os.path.join(OUT, 'nested_magic.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    w()
    w('写入：cfg_parsed/nested_magic.txt · nested_magic.json')


main()
