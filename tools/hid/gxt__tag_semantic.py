# -*- coding: utf-8 -*-
"""
A-13 语义定位：把真 TAG 的载荷与「已知语义」对齐。

已知语义锚点（来自项目已有资料）：
  A. 128 中心电容基线   -> 载荷应围绕 0x80(128) 波动，且长度 ≈ 2×通道数
  B. 通道/引脚映射      -> 载荷是 0x01,0x02,0x03… 递增序列
  C. 时序/时长          -> u16 常量 0x0190(400) / 0x0258(600) / 0x001E(30) / 0x0032(50)
  D. 厂商字符串         -> ASCII
  E. 版本/日期          -> 十进制数字对（如 20240307）

本脚本做四件事：
  1. 对每个真 TAG，判定属于哪一类（A–E）。
  2. 重点：找出含 400/600/30/50 时长常量的 TAG  -> A-14 的入口。
  3. 找出「递增序列」TAG -> 通道映射。
  4. 找出「围绕 128」TAG -> 基线表。
  最终输出一张「TAG -> 语义（含置信度）」表。
"""
import os, json, struct, re, math
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(HERE, 'cfg')
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)

FILES = ['sid0.bin', 'sid2.bin', 'sid3.bin']
BEST = {'sid0.bin': 0x38, 'sid2.bin': 0x40, 'sid3.bin': 0x40}

# 已知时长常量（A-14 目标）
DURATIONS = {
    0x0190: '400ms', 0x0258: '600ms', 0x001E: '30', 0x0032: '50',
    0x0064: '100', 0x00C8: '200', 0x012C: '300', 0x01F4: '500',
    0x03E8: '1000', 0x000A: '10', 0x0014: '20', 0x0060: '96',
    0x00FA: '250', 0x0080: '128',
}

L = []
def w(s=''):
    L.append(s)
    print(s)


def walk_keep(data, start):
    """返回剔除「TAG=0 & LEN=0」填充后的块，同时记录填充位点。"""
    keep, pads = [], []
    i, n = start, len(data)
    while i < n:
        if i + 2 > n:
            break
        tag, ln = data[i], data[i + 1]
        j = i + 2 + ln
        if j > n:
            break
        if tag == 0 and ln == 0:
            pads.append((i, 2))
        else:
            keep.append((i, tag, ln, data[i + 2:j]))
        i = j
    return keep, pads


def ascii_ratio(b):
    return sum(1 for x in b if 32 <= x < 127) / len(b) if b else 0.0


def inc_ratio(b):
    """相邻字节 +1 递增的比例"""
    if len(b) < 2:
        return 0.0
    return sum(1 for k in range(1, len(b)) if b[k] == (b[k - 1] + 1) & 0xFF) / (len(b) - 1)


def near128_ratio_u16(b, lo=100, hi=201):
    if len(b) < 4:
        return 0.0
    u = [struct.unpack_from('<H', b, k)[0] for k in range(0, len(b) - 1, 2)]
    return sum(1 for x in u if lo <= x <= hi) / len(u) if u else 0.0


def monotone_u16(b):
    """u16 序列的单调性（递增或递减）"""
    if len(b) < 6:
        return 0.0, ''
    u = [struct.unpack_from('<H', b, k)[0] for k in range(0, len(b) - 1, 2)]
    if len(u) < 3:
        return 0.0, ''
    up = sum(1 for k in range(1, len(u)) if u[k] > u[k - 1])
    dn = sum(1 for k in range(1, len(u)) if u[k] < u[k - 1])
    m = max(up, dn) / (len(u) - 1)
    return m, ('↑' if up > dn else '↓')


def main():
    w('=' * 78)
    w('A-13 语义定位：TAG -> 语义')
    w('=' * 78)

    dat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(HERE, fn)
        dat[fn] = open(p, 'rb').read()

    keepall = {}
    for fn in FILES:
        keepall[fn], _ = walk_keep(dat[fn], BEST[fn])

    # ---------- 1. 语义分类 ----------
    w()
    w('### 1. TAG 语义分类（按载荷指纹）')
    w()
    w('| TAG | 出现 | 典型 LEN | 指纹 | 语义判定 | 置信 |')
    w('|---|---|---|---|---|---|')
    taginfo = {}
    for fn in FILES:
        for (o, t, l, p) in keepall[fn]:
            d = taginfo.setdefault(t, {'n': 0, 'lens': [], 'sites': [], 'ar': [], 'ir': [],
                                       'n128': [], 'mono': []})
            d['n'] += 1
            d['lens'].append(l)
            d['sites'].append((fn, o, l))
            d['ar'].append(ascii_ratio(p))
            d['ir'].append(inc_ratio(p))
            d['n128'].append(near128_ratio_u16(p))
            m, dirn = monotone_u16(p)
            d['mono'].append((m, dirn))

    for t, d in sorted(taginfo.items()):
        lens = sorted(set(d['lens']))
        # 取最长的那个载荷做指纹
        cands = [(fn, o, l) for (fn, o, l) in d['sites']]
        bestsite = max(cands, key=lambda x: x[2])
        p = dict(((fn, o), None) for (fn, o) in [])
        pl = None
        for fn in FILES:
            for (o, t2, l2, p2) in keepall[fn]:
                if t2 == t and (fn, o, l2) == bestsite:
                    pl = p2
        if pl is None:
            continue
        ar = ascii_ratio(pl)
        ir = inc_ratio(pl)
        n128 = near128_ratio_u16(pl)
        mono, mdir = monotone_u16(pl)
        tags_txt = []
        conf = '低'
        if ar > 0.6:
            tags_txt.append('ASCII 文本')
            conf = '高'
        if ir > 0.5 and len(pl) >= 8:
            tags_txt.append('递增序列(通道映射)')
            conf = '高'
        if n128 > 0.5 and len(pl) >= 8:
            tags_txt.append('128 附近 u16(基线/电容)')
            conf = '高'
        if mono > 0.7 and len(pl) >= 8:
            tags_txt.append('u16 单调%s(系数/时序)' % mdir)
            conf = '中'
        if not tags_txt:
            tags_txt.append('未定（混合/二进制）')
        w('| `0x%02X` | %d | %s | ASCII %.2f / 递增 %.2f / 128 %.2f / 单调 %.2f%s | %s | %s |'
          % (t, d['n'],
             ','.join(str(x) for x in lens[:4]) + ('…' if len(lens) > 4 else ''),
             ar, ir, n128, mono, mdir, ' + '.join(tags_txt), conf))

    # ---------- 2. A-14 入口：时长常量定位 ----------
    w()
    w('### 2. 🎯 A-14 入口：u16 时长常量出现在哪些 TAG 里')
    w()
    w('扫描每个载荷里的 u16LE，匹配已知时长常量表。')
    w()
    w('| 常量 | 含义 | 文件 | 块偏移 | TAG | 位置(in payload) |')
    w('|---|---|---|---|---|---|')
    hits = defaultdict(list)
    for fn in FILES:
        for (o, t, l, p) in keepall[fn]:
            for k in range(0, len(p) - 1):
                v = struct.unpack_from('<H', p, k)[0]
                if v in DURATIONS and k % 2 == 0:
                    hits[v].append((fn, o, t, k, l))
    for v in sorted(hits, key=lambda x: -len(hits[x])):
        sites = hits[v]
        for (fn, o, t, k, l) in sites[:6]:
            w('| `0x%04X` | %s | %s | 0x%04X | `0x%02X` | +%d (LEN=%d) |'
              % (v, DURATIONS[v], fn, o, t, k, l))
        if len(sites) > 6:
            w('| | | … 其余 %d 处 | | | |' % (len(sites) - 6))
    w()
    w('**时长常量命中总表**：')
    for v in sorted(hits, key=lambda x: -len(hits[x])):
        fs = Counter(s[0] for s in hits[v])
        w('- `0x%04X` (%s) × %d 处 · 分布 %s'
          % (v, DURATIONS[v], len(hits[v]),
             ', '.join('%s:%d' % (k[:4], n) for k, n in fs.most_common())))

    # ---------- 3. 用已知语义锚点反查 ----------
    w()
    w('### 3. 🎯🎯 关键：三份 cfg 都出现的「时长候选」同一 TAG 比对')
    w()
    # 找同时含 400 或 600 的 TAG
    dur_tags = set()
    for v in (0x0190, 0x0258):
        for (fn, o, t, k, l) in hits.get(v, []):
            dur_tags.add(t)
    if dur_tags:
        w('含 400ms 或 600ms 的 TAG：%s' % ', '.join('`0x%02X`' % t for t in sorted(dur_tags)))
        w()
        for t in sorted(dur_tags):
            w('#### TAG `0x%02X` 全位点' % t)
            w()
            w('| 文件 | 偏移 | LEN | 载荷(全) |')
            w('|---|---|---|---|')
            for fn in FILES:
                for (o, t2, l, p) in keepall[fn]:
                    if t2 != t:
                        continue
                    if l <= 48:
                        w('| %s | 0x%04X | %d | `%s` |' % (fn, o, l, p.hex(' ')))
                    else:
                        w('| %s | 0x%04X | %d | `%s` … |' % (fn, o, l, p[:48].hex(' ')))
    else:
        w('⚠️ 400/600ms 常量未落在任何「真 TAG」内 —— 可能落在填充区或被 TLV 切错。')

    # ---------- 4. 填充区里有没有被切掉的东西 ----------
    w()
    w('### 4. 填充区内容检查（是否藏着被误判为填充的真数据）')
    w()
    for fn in FILES:
        _, pads = walk_keep(dat[fn], BEST[fn])
        data = dat[fn]
        # 填充区实际覆盖的字节：从每个填充块往前看有没有非零
        nz = 0
        for (o, ln) in pads:
            # 填充块只有 2 字节头，看看它后面实际有多少个连续 0
            k = o
            while k < len(data) and data[k] == 0:
                k += 1
            run = k - o
            if run > 2:
                nz += 1
        w('- %s：填充块 %d 个，其中 %d 个后面跟着 >2 字节的连续 0 ⇒ 确实是零填充'
          % (fn, len(pads), nz))

    # ---------- 5. sid0 的 0x00 大块（214B）单独看 ----------
    w()
    w('### 5. 唯一的大块：sid0 @0x003A TAG=0x00 LEN=214 —— 单独解析')
    w()
    for fn in FILES:
        for (o, t, l, p) in keepall[fn]:
            if l >= 100:
                w('#### %s @0x%04X  TAG=`0x%02X`  LEN=%d' % (fn, o, t, l))
                w()
                # 按 u16 打印
                u = [struct.unpack_from('<H', p, k)[0] for k in range(0, len(p) - 1, 2)]
                for row in range(0, min(len(u), 64), 8):
                    w('  +%3d: %s' % (row * 2, ' '.join('%5d' % x for x in u[row:row + 8])))
                w()

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'tag_semantic.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'duration_hits': {'%04X' % v: [[f, o, '%02X' % t, k, l] for (f, o, t, k, l) in s]
                                 for v, s in hits.items()}},
              open(os.path.join(OUT, 'tag_semantic.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    w()
    w('写入：cfg_parsed/tag_semantic.txt · tag_semantic.json')


main()
