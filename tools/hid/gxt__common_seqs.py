# -*- coding: utf-8 -*-
"""
A-13 真正的方法：**跨文件重复序列**搜索（不预设语法）

教训：上一版找「u16 ∈ 0x50xx-0x5Fxx 魔数」失败，因为 0x50xx 是常见字节组合。
正确做法：不预设任何语法，直接找「在 ≥2 份不同厂商 cfg 里逐字节相同」的
          **长重复片段**。这些片段必然是格式的一部分（厂商各自填不同值，
          但共用的模板/常量会保留）。

步骤：
  R1 对每对文件，用滚动哈希找长度 ≥ 12 字节的完全匹配片段。
  R2 合并重叠片段成「共有区域」。
  R3 对每个共有区域，检查它落在哪个一级 TLV 块内、相对位置、是否在同一 TAG 下。
  R4 统计：共有区域是否显著集中在某些 TAG → 那些 TAG 就是「跨厂商模板」。
"""
import os, struct, json, hashlib
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(HERE, 'cfg')
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)

FILES = ['sid0.bin', 'sid2.bin', 'sid3.bin']
BEST = {'sid0.bin': 0x38, 'sid2.bin': 0x40, 'sid3.bin': 0x40}
MINLEN = 12

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


def common_substrings(a, b, minlen):
    """找 a / b 之间长度 >= minlen 的公共子串（贪心最长优先，不重叠）。"""
    a_idx = defaultdict(list)
    for L2 in range(minlen, len(a) + 1):
        if len(a) - L2 + 1 > 200000:
            break
    # 简单实现：对 a 中每个 minlen 窗口建索引，然后在 b 里扩展
    idx = defaultdict(list)
    for k in range(0, len(a) - minlen + 1):
        idx[a[k:k + minlen]].append(k)
    found = []
    used_b = [False] * len(b)
    for k in range(0, len(b) - minlen + 1):
        key = b[k:k + minlen]
        if key not in idx:
            continue
        if any(used_b[k:k + minlen]):
            continue
        for ka in idx[key]:
            # 双向扩展
            s, e = 0, minlen
            while ka - s - 1 >= 0 and k - s - 1 >= 0 and a[ka - s - 1] == b[k - s - 1]:
                s += 1
            while ka + e < len(a) and k + e < len(b) and a[ka + e] == b[k + e]:
                e += 1
            found.append((ka - s, k - s, e + s))
            for t in range(k - s, min(k - s + e + s, len(b))):
                used_b[t] = True
            break
    return found


def merge(spans):
    if not spans:
        return []
    spans = sorted(spans)
    out = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [tuple(x) for x in out]


def main():
    w('=' * 78)
    w('A-13 跨文件重复序列搜索（不预设语法）')
    w('=' * 78)
    w()
    w('最小匹配长度 = %d 字节。' % MINLEN)

    dat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(HERE, fn)
        dat[fn] = open(p, 'rb').read()

    keep = {fn: walk_keep(dat[fn], BEST[fn]) for fn in FILES}

    pairs = [('sid0.bin', 'sid2.bin'), ('sid0.bin', 'sid3.bin'), ('sid2.bin', 'sid3.bin')]
    result = {}
    for fa, fb in pairs:
        a, b = dat[fa], dat[fb]
        ms = common_substrings(a, b, MINLEN)
        # 只保留长度 >= MINLEN 的
        ms = [(x, y, ln) for (x, y, ln) in ms if ln >= MINLEN]
        result[(fa, fb)] = ms
        w()
        w('### %s ↔ %s ：%d 个匹配片段（≥%d B）' % (fa, fb, len(ms), MINLEN))
        w()
        if not ms:
            w('（无）')
            continue
        w('| %s 偏移 | %s 偏移 | 长度 | 内容 hex |' % (fa, fb))
        w('|---|---|---|---|')
        for (x, y, ln) in sorted(ms, key=lambda t: -t[2])[:30]:
            body = a[x:x + ln]
            txt = body.decode('latin-1')
            printable = all(32 <= c < 127 for c in body)
            w('| 0x%04X | 0x%04X | %d | `%s`%s |'
              % (x, y, ln, body[:32].hex(' '), ' …' if ln > 32 else ''))
        w()
        w('**最长 5 个匹配**（含可读文本标注）：')
        for (x, y, ln) in sorted(ms, key=lambda t: -t[2])[:5]:
            body = a[x:x + ln]
            w('- %s@0x%04X = %s@0x%04X · %d B · `%s`'
              % (fa, x, fb, y, ln, ''.join(chr(c) if 32 <= c < 127 else '.' for c in body[:64])))

    # ---------- 汇总：三份全共有 ----------
    w()
    w('### 🎯 三份文件全都含有的片段（最强证据）')
    w()
    s02 = set(dat['sid0.bin'][x:x + ln] for (x, y, ln) in result[('sid0.bin', 'sid2.bin')])
    s03 = set(dat['sid0.bin'][x:x + ln] for (x, y, ln) in result[('sid0.bin', 'sid3.bin')])
    both = {v for v in s02 if v in s03} | {v for v in s03 if v in s02}
    w('sid0∩sid2 = %d 片段；sid0∩sid3 = %d 片段；三份全有 = %d 片段'
      % (len(s02), len(s03), len(both)))
    w()
    w('| 长度 | 内容 | 在 sid0 的位置 | 在 sid2 的位置 | 在 sid3 的位置 |')
    w('|---|---|---|---|---|')
    for v in sorted(both, key=lambda x: -len(x))[:25]:
        def where(fn):
            i = dat[fn].find(v)
            return '0x%04X' % i if i >= 0 else '—'
        w('| %d | `%s` | %s | %s | %s |'
          % (len(v), v[:32].hex(' '), where('sid0.bin'), where('sid2.bin'), where('sid3.bin')))

    # ---------- 落在哪个 TAG ----------
    w()
    w('### 共有片段落在哪些一级 TAG 内（判断哪些 TAG 是跨厂商模板）')
    w()
    taghits = Counter()
    for (fa, fb) in pairs:
        for (x, y, ln) in result[(fa, fb)]:
            for (o, t, l, p) in keep[fa]:
                if o <= x < o + 2 + l:
                    taghits[t] += 1
                    break
    w('| TAG | 被共有片段命中的次数 | 该 TAG 出现总次数 | 命中率 |')
    w('|---|---|---|---|')
    tot = Counter(t for fn in FILES for (o, t, l, p) in keep[fn])
    for t, n in taghits.most_common(20):
        w('| `0x%02X` | %d | %d | %.2f |' % (t, n, tot.get(t, 0), n / max(1, tot.get(t, 0))))

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'common_seqs.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'pairs': {'%s|%s' % k: [[x, y, ln] for (x, y, ln) in v]
                         for k, v in result.items()}},
              open(os.path.join(OUT, 'common_seqs.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    w()
    w('写入：cfg_parsed/common_seqs.txt · common_seqs.json')


main()
