# -*- coding: utf-8 -*-
"""
A-13 关键追问：0x00 到底是「TAG=0」还是「填充/终止符」？

观察：TAG=0x00 的块在 sid0/sid2/sid3 里分别占 47/84、10/…、27/… —— 极高频。
如果 0x00 是填充，那么 TLV 模型要改写成：
   [TAG!=0][LEN][payload]  记录，记录之间用 0x00 填充到某个对齐
或者
   [TAG][LEN][payload] 但 LEN=0 && TAG=0 表示「对齐填充」

检验：
  P1 LEN=0 的块里 TAG 的分布：若只有 0x00/0x80 是「空」，其余 TAG 的 LEN=0 就是真字段。
  P2 TAG=0x00 的块，其后紧跟的字节是什么？若总是 0x00 则确实是填充串。
  P3 把所有 TAG=0x00 且 LEN=0 的块剔除后，剩余块是否构成一个**连续无空洞**的流？
  P4 剔除后覆盖率是多少？若接近 100% 且无截断，则模型大幅改善。
  P5 对齐检验：剔除填充后，块起始地址是否对齐到 2/4？
"""
import os, json, struct
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


def walk_raw(data, start):
    blocks, i, n = [], start, len(data)
    while i < n:
        if i + 2 > n:
            blocks.append((i, data[i], None, None, 'TRUNC'))
            break
        tag = data[i]
        ln = data[i + 1]
        j = i + 2 + ln
        if j > n:
            blocks.append((i, tag, ln, None, 'TRUNC'))
            break
        blocks.append((i, tag, ln, data[i + 2:j], None))
        i = j
    return blocks


def main():
    w('=' * 78)
    w('A-13 追问：0x00 是 TAG 还是填充？')
    w('=' * 78)

    dat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(HERE, fn)
        dat[fn] = open(p, 'rb').read()

    # ---------- P1 LEN=0 的块的 TAG 分布 ----------
    w()
    w('### P1 LEN=0 的块 —— TAG 分布')
    w()
    w('| 文件 | LEN=0 块数 | 其中 TAG=0x00 | 其中 TAG=0x80 | 其他 TAG |')
    w('|---|---|---|---|---|')
    for fn in FILES:
        blk = walk_raw(dat[fn], BEST[fn])
        z = [(o, t) for (o, t, l, p, e) in blk if e is None and l == 0]
        c = Counter(t for _, t in z)
        others = {k: v for k, v in c.items() if k not in (0x00, 0x80)}
        w('| %s | %d | %d | %d | %s |'
          % (fn, len(z), c.get(0, 0), c.get(0x80, 0),
             ', '.join('`%02X`×%d' % (k, v) for k, v in sorted(others.items())) or '—'))

    # ---------- P2 TAG=0x00 块之后紧跟什么 ----------
    w()
    w('### P2 TAG=0x00 块之后的字节（判断是否填充串）')
    w()
    w('| 文件 | 后续字节分布（top 6） | 结论 |')
    w('|---|---|---|')
    for fn in FILES:
        data = dat[fn]
        blk = walk_raw(data, BEST[fn])
        nxt = Counter()
        for (o, t, l, p, e) in blk:
            if e is not None or t != 0x00:
                continue
            end = o + 2 + (l or 0)
            if end < len(data):
                nxt[data[end]] += 1
        top = nxt.most_common(6)
        zratio = nxt.get(0, 0) / max(1, sum(nxt.values()))
        w('| %s | %s | %s |'
          % (fn, ', '.join('`%02X`×%d' % kv for kv in top),
             '★ 后续多为 0x00 ⇒ 填充' if zratio > 0.5 else '后续多样 ⇒ 像真 TAG'))

    # ---------- P3 剔除 TAG=0 & LEN=0 后，剩余流是否连续 ----------
    w()
    w('### P3 剔除「TAG=0x00 且 LEN=0」的填充块后，剩余流是否连续无空洞')
    w()
    w('| 文件 | 原块数 | 剔除数 | 保留块数 | 空洞字节数 | 剩余覆盖率 | 截断 |')
    w('|---|---|---|---|---|---|---|')
    keepall = {}
    for fn in FILES:
        data = dat[fn]
        blk = walk_raw(data, BEST[fn])
        keep = [(o, t, l, p) for (o, t, l, p, e) in blk
                if e is None and not (t == 0x00 and l == 0)]
        # 空洞：保留块之间未覆盖的字节
        holes = 0
        prev = BEST[fn]
        for (o, t, l, p) in keep:
            if o > prev:
                holes += o - prev
            prev = o + 2 + l
        if prev < len(data):
            holes += len(data) - prev
        cov = sum(2 + l for (_, _, l, _) in keep)
        trunc = sum(1 for x in blk if x[4])
        keepall[fn] = keep
        w('| %s | %d | %d | %d | %d | %.1f%% | %d |'
          % (fn, len(blk), len(blk) - len(keep), len(keep), holes,
             100.0 * cov / len(data), trunc))

    # ---------- P4 剔除后 TAG/LEN 统计 ----------
    w()
    w('### P4 剔除填充后的 TAG 表（这才是「真配置项」）')
    w()
    tagstat = defaultdict(lambda: {'n': 0, 'lens': [], 'files': Counter(), 'pay': []})
    for fn, keep in keepall.items():
        for (o, t, l, p) in keep:
            s = tagstat[t]
            s['n'] += 1
            s['lens'].append(l)
            s['files'][fn] += 1
            if p is not None and len(s['pay']) < 8:
                s['pay'].append((fn, o, p))
    w('| TAG | 次数 | LEN 取值 | 定/变 | 分布 sid0/sid2/sid3 | 载荷样例 |')
    w('|---|---|---|---|---|---|')
    for t, s in sorted(tagstat.items()):
        lens = sorted(set(s['lens']))
        fixed = '定长' if len(lens) == 1 else '变长'
        sm = s['pay'][0][2] if s['pay'] else b''
        w('| `0x%02X` | %d | %s | %s | %d/%d/%d | `%s`%s |'
          % (t, s['n'], ','.join(str(x) for x in lens[:6]) + ('…' if len(lens) > 6 else ''),
             fixed, s['files'].get('sid0.bin', 0), s['files'].get('sid2.bin', 0),
             s['files'].get('sid3.bin', 0),
             sm[:20].hex(' '), '…' if len(sm) > 20 else ''))
    w()
    w('**真 TAG 数 = %d**（剔除填充后）' % len(tagstat))

    # ---------- P5 对齐 ----------
    w()
    w('### P5 剔除填充后，块起始的 mod 2 / mod 4 对齐')
    w()
    w('| 文件 | mod 2 | mod 4 | 结论 |')
    w('|---|---|---|---|')
    for fn, keep in keepall.items():
        m2 = Counter(o % 2 for (o, _, _, _) in keep)
        m4 = Counter(o % 4 for (o, _, _, _) in keep)
        w('| %s | %s | %s | %s |'
          % (fn, ', '.join('%d:%d' % kv for kv in sorted(m2.items())),
             ', '.join('%d:%d' % kv for kv in sorted(m4.items())),
             '★ 全偶数' if m2.get(1, 0) == 0 else '混')) 
    w()
    w('注：`o` 是块起始**绝对**偏移。若全偶数，说明配置项按 2 字节对齐 —— 强烈支持真结构。')

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'tag_padding_check.txt'), 'w', encoding='utf-8').write(txt)
    w()
    w('写入：cfg_parsed/tag_padding_check.txt')


main()
