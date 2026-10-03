# -*- coding: utf-8 -*-
"""
A-13 定案：54 字节跨厂商模板的完整结构。

铁证（common_seqs）：
  sid0@0x036A == sid3@0x053A，逐字节相同，长度 54 B：
    00 00 00 00 | 30 5c | 0a 00 14 00 50 00 20 03 e8 03 d0 07 40 1f 10 27 |
    58 02 2d 00 90 01 | 00 00 | 88 13 00 00 10 27 00 00 | f4 ...

这次不是"猜魔数"，而是**先用跨文件重复把它钉死**，再解释结构。

结构解释（待验证）：
  [00 00 00 00]      前导
  [30 5c]            = 0x5C30，疑似子块标识（低字节 = 类型，高字节 = 0x5C 家族）
  [0a 00]            = 10       <- u16 计数？或第一个值
  [14 00]            = 20
  [50 00]            = 80
  [20 03]            = 800
  [e8 03]            = 1000
  [d0 07]            = 2000
  [40 1f]            = 8000
  [10 27]            = 10000
  [58 02]            = 600
  [2d 00]            = 45
  [90 01]            = 400     <- 400ms!
  [00 00]            = 0
  [88 13]            = 5000
  [00 00]            = 0
  [10 27]            = 10000
  [00 00]            = 0
  [f4 ...]           后续被截断

关键检验：
  K1 这 54 字节在 sid0/sid3 里的**前后文**是什么？（是不是同一个一级 TAG 的同一子位置）
  K2 它的内部是不是「u16 单调阶梯」？
  K3 sid2（无触觉）里有没有对应结构？若没有 → 这就是触觉专用块。
"""
import os, struct, json
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(HERE, 'cfg')
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)

FILES = ['sid0.bin', 'sid2.bin', 'sid3.bin']
BEST = {'sid0.bin': 0x38, 'sid2.bin': 0x40, 'sid3.bin': 0x40}

# 铁证片段
TEMPLATE = bytes.fromhex(
    '00 00 00 00 30 5c 0a 00 14 00 50 00 20 03 e8 03 '
    'd0 07 40 1f 10 27 58 02 2d 00 90 01 00 00 88 13 '
    '00 00 10 27 00 00 f4')

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


def locate(keep, off):
    for (o, t, l, p) in keep:
        if o <= off < o + 2 + l:
            return (o, t, l, off - (o + 2))
    return None


def main():
    w('=' * 78)
    w('A-13 定案：54 字节跨厂商模板')
    w('=' * 78)
    dat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(HERE, fn)
        dat[fn] = open(p, 'rb').read()

    keep = {fn: walk_keep(dat[fn], BEST[fn]) for fn in FILES}

    w()
    w('### K1 模板定位：落到哪个一级 TAG 的哪个相对位置')
    w()
    w('| 文件 | 模板偏移 | 一级块偏移 | TAG | 一级 LEN | 在 payload 内相对偏移 |')
    w('|---|---|---|---|---|---|')
    for fn in FILES:
        idx = 0
        while True:
            i = dat[fn].find(TEMPLATE, idx)
            if i < 0:
                break
            loc = locate(keep[fn], i)
            if loc:
                o, t, l, rel = loc
                w('| %s | 0x%04X | 0x%04X | `0x%02X` | %d | +%d |' % (fn, i, o, t, l, rel))
            else:
                w('| %s | 0x%04X | — | — | — | — |' % (fn, i))
            idx = i + 1

    w()
    w('### K2 模板内部：u16 单调性')
    w()
    u = [struct.unpack_from('<H', TEMPLATE, k)[0] for k in range(0, len(TEMPLATE) - 1, 2)]
    w('```')
    w('偏移  值      标注')
    NAMES = {0x0190: '★400', 0x0258: '★600', 0x03E8: '1000', 0x012C: '300',
             0x01F4: '500', 0x0064: '100', 0x00C8: '200', 0x001E: '30',
             0x0032: '50', 0x0014: '20', 0x000A: '10', 0x1388: '5000',
             0x2710: '10000', 0x1F40: '8000', 0x07D0: '2000', 0x0320: '800'}
    for k in range(0, len(TEMPLATE) - 1, 2):
        v = struct.unpack_from('<H', TEMPLATE, k)[0]
        w('  +%-3d %-8d %s' % (k, v, NAMES.get(v, '')))
    w('```')
    w()
    w('u16 序列：%s' % u)
    # 单调性
    inc = all(u[k] >= u[k - 1] for k in range(1, len(u))) if len(u) > 1 else False
    w()
    w('整体单调不减：**%s**' % ('是 ✅' if inc else '否 ❌'))
    # 只看从 0x5C30 之后的 12 个值
    sub = u[2:14]
    w('从 `0x5C30` 之后的 12 个 u16：%s' % sub)
    inc2 = all(sub[k] > sub[k - 1] for k in range(1, len(sub)))
    w('该 12 个值严格递增：**%s**' % ('是 ✅ 阶梯特征' if inc2 else '否 ❌'))

    w()
    w('### K3 sid2（无触觉器件的板子）里有没有对应结构')
    w()
    w('- 完整 54 B 模板：s in sid2 = %s' % ('有 ❌' if TEMPLATE in dat['sid2.bin'] else '无 ✅'))
    # 找部分匹配
    parts = [('30 5c', 2), ('0a 00 14 00 50 00 20 03', 8), ('58 02 2d 00 90 01', 6),
             ('10 27 58 02', 4)]
    for hx, ln in parts:
        b = bytes.fromhex(hx)
        w('- `%s` (%dB)：sid0=%d · sid2=%d · sid3=%d'
          % (hx, ln, dat['sid0.bin'].count(b), dat['sid2.bin'].count(b), dat['sid3.bin'].count(b)))

    w()
    w('### K4 模板前后各 24 字节的上下文（看边界）')
    w()
    for fn in FILES:
        i = dat[fn].find(TEMPLATE)
        if i < 0:
            w('- %s：无' % fn)
            continue
        before = dat[fn][max(0, i - 24):i]
        after = dat[fn][i + len(TEMPLATE):i + len(TEMPLATE) + 24]
        w('```')
        w('%s @0x%04X' % (fn, i))
        w('  前 24: %s' % before.hex(' '))
        w('  模板 : %s' % TEMPLATE.hex(' '))
        w('  后 24: %s' % after.hex(' '))
        w('```')

    w()
    w('### K5 全 cfg 里 `xx 5c` / `xx 5d` / `xx 5e` / `xx 5f` 家族的分布')
    w()
    fam = {0x5C: '5C', 0x5D: '5D', 0x5E: '5E', 0x5F: '5F'}
    w('| 文件 | 0x5Cxx | 0x5Dxx | 0x5Exx | 0x5Fxx | 说明 |')
    w('|---|---|---|---|---|---|')
    for fn in FILES:
        data = dat[fn]
        c = Counter()
        for k in range(0, len(data) - 1):
            v = struct.unpack_from('<H', data, k)[0]
            if (v >> 8) in fam:
                c[v >> 8] += 1
        w('| %s | %d | %d | %d | %d | 随机基线 ≈ %d/库 |'
          % (fn, c.get(0x5C, 0), c.get(0x5D, 0), c.get(0x5E, 0), c.get(0x5F, 0),
             len(data) // 256))

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'template_54.txt'), 'w', encoding='utf-8').write(txt)
    w()
    w('写入：cfg_parsed/template_54.txt')


main()
