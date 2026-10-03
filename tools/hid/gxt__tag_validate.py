# -*- coding: utf-8 -*-
"""
A-13 校验（自证伪优先）：TLV 模型真的成立吗？

危险的替代解释：如果 LEN 字段是「冗余的」，那么 [TAG][LEN] 模型会因为
TAG/LEN 都是任意字节而"总能"遍历下去 —— 覆盖率 96% 就成了必然结果而非证据。

必须做的三重检验：
  T1 随机对照：把 cfg 的字节随机打乱（保持分布），同样的遍历器覆盖率是多少？
     -> 若随机数据也能覆盖 ~96%，则 TLV 模型【无信息量】。
  T2 结构性：TAG 分布是否显著偏离均匀 / 是否集中在少数值？
     -> 真格式的 TAG 种类应远少于 256，且高频 TAG 有语义理由。
  T3 长度合理性：块长是否集中在少数值（真配置的字段长度是离散的）？
     -> 比较真实 cfg 与随机打乱的 LEN 熵。
  T4 边界对齐：块起始地址是否更倾向某些模值？（真格式常有对齐）
  T5 跨文件同构：同一个 TAG 的两份不同厂商文件里是否给出【语义一致】的载荷？
     -> 这才是最终证据。
"""
import os, random, math, struct, json
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_DIR = os.path.join(HERE, 'cfg')
OUT = os.path.join(HERE, 'cfg_parsed')
os.makedirs(OUT, exist_ok=True)
random.seed(20260930)

FILES = ['sid0.bin', 'sid2.bin', 'sid3.bin']
BEST = {'sid0.bin': 0x38, 'sid2.bin': 0x40, 'sid3.bin': 0x40}

L = []
def w(s=''):
    L.append(s)
    print(s)


def walk(data, start):
    blocks, i, n = [], start, len(data)
    while i < n:
        tag = data[i]
        if i + 2 > n:
            break
        ln = data[i + 1]
        j = i + 2 + ln
        if j > n:
            blocks.append((i, tag, ln, None, 'TRUNC'))
            break
        blocks.append((i, tag, ln, data[i + 2:j], None))
        i = j
    cov = sum(2 + ln for (_, _, ln, p, e) in blocks if e is None)
    return blocks, cov


def entropy(counter, n):
    if n <= 0:
        return 0.0
    h = 0.0
    for v in counter.values():
        p = v / n
        h -= p * math.log2(p)
    return h


def main():
    w('=' * 78)
    w('A-13 校验：TLV 模型是否真的有信息量？（自证伪）')
    w('=' * 78)

    dat = {}
    for fn in FILES:
        p = os.path.join(CFG_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(HERE, fn)
        dat[fn] = open(p, 'rb').read()

    # ---------- T1 随机对照 ----------
    w()
    w('### T1 🔴 随机对照 —— 决定性：随机数据的覆盖率是多少？')
    w()
    w('如果一份**随机打乱**的数据用同一遍历器也能覆盖 ~96%，那 TLV 模型就是**同义反复**，')
    w('覆盖率就不是证据。反之则是真结构。')
    w()
    w('| 文件 | 真实覆盖 | 真实块数 | 打乱后覆盖(20 次均值) | 打乱后块数 | 差值 | 结论 |')
    w('|---|---|---|---|---|---|---|')
    t1 = {}
    for fn in FILES:
        data = dat[fn]
        start = BEST[fn]
        blk, cov = walk(data, start)
        real = cov / len(data)
        covs, blks = [], []
        for _ in range(20):
            sh = bytearray(data)
            body = list(sh[start:])
            random.shuffle(body)
            sh[start:] = bytes(body)
            b2, c2 = walk(bytes(sh), start)
            covs.append(c2 / len(data))
            blks.append(len(b2))
        mc = sum(covs) / len(covs)
        mb = sum(blks) / len(blks)
        verdict = '✅ 真结构' if real - mc > 0.10 else ('⚠️ 弱' if real - mc > 0.03 else '❌ 无信息量')
        t1[fn] = {'real': real, 'shuf': mc, 'real_blocks': len(blk), 'shuf_blocks': mb}
        w('| %s | %.1f%% | %d | %.1f%% ± %.1f%% | %.0f | %+.1f pt | %s |'
          % (fn, 100 * real, len(blk), 100 * mc,
             100 * (max(covs) - min(covs)) / 2, mb, 100 * (real - mc), verdict))

    # ---------- T2 TAG 分布规律性 ----------
    w()
    w('### T2 TAG 分布的规律性')
    w()
    w('| 文件 | 不同 TAG 数 | TAG 熵 (max 8.0) | 高频 TAG | 高频 TAG 占比 |')
    w('|---|---|---|---|---|')
    for fn in FILES:
        blk, _ = walk(dat[fn], BEST[fn])
        tags = [t for (_, t, _, _, e) in blk if e is None]
        c = Counter(tags)
        h = entropy(c, len(tags))
        top = c.most_common(5)
        w('| %s | %d / 256 | %.2f | %s | %.0f%% |'
          % (fn, len(c), h,
             ', '.join('`%02X`×%d' % (k, v) for k, v in top),
             100.0 * sum(v for _, v in top) / max(1, len(tags))))

    # ---------- T3 LEN 分布 ----------
    w()
    w('### T3 LEN 分布（真配置的字段长度应离散集中）')
    w()
    w('| 文件 | 不同 LEN 数 | LEN 熵 | 最常见 LEN | 与随机对照 |')
    w('|---|---|---|---|---|')
    for fn in FILES:
        blk, _ = walk(dat[fn], BEST[fn])
        lns = [l for (_, _, l, _, e) in blk if e is None]
        c = Counter(lns)
        h = entropy(c, len(lns))
        # 随机对照：打乱后
        data = dat[fn]
        sh = bytearray(data); body = list(sh[BEST[fn]:]); random.shuffle(body)
        sh[BEST[fn]:] = bytes(body)
        b2, _ = walk(bytes(sh), BEST[fn])
        lns2 = [l for (_, _, l, _, e) in b2 if e is None]
        c2 = Counter(lns2)
        h2 = entropy(c2, len(lns2))
        w('| %s | %d | %.2f | %s | 随机 %.2f (%s) |'
          % (fn, len(c), h, ', '.join('%d×%d' % (k, v) for k, v in c.most_common(4)),
             h2, '更离散 ✅' if h < h2 - 0.3 else '相近 ❌'))

    # ---------- T4 块起始对齐 ----------
    w()
    w('### T4 块起始偏移的对齐倾向')
    w()
    w('| 文件 | 块起始 mod 4 分布 | mod 8 | 结论 |')
    w('|---|---|---|---|')
    for fn in FILES:
        blk, _ = walk(dat[fn], BEST[fn])
        offs = [o for (o, _, _, _, e) in blk if e is None]
        m4 = Counter(o % 4 for o in offs)
        m8 = Counter(o % 8 for o in offs)
        ent4 = entropy(m4, len(offs))
        w('| %s | %s | %s | %s |'
          % (fn, ', '.join('%d:%d' % (k, v) for k, v in sorted(m4.items())),
             ', '.join('%d:%d' % (k, v) for k, v in sorted(m8.items())),
             '均匀（无对齐）' if ent4 > 1.9 else '★ 有对齐倾向'))

    # ---------- T5 跨文件同 TAG 语义一致 ----------
    w()
    w('### T5 🎯🎯 跨文件同 TAG 的语义一致性（最终证据）')
    w()
    w('取「在 ≥2 份文件中出现」的 TAG，比较载荷的**统计指纹**是否一致：')
    w('长度、数值范围、ASCII 率、字节多样性。')
    w()
    per = {}
    for fn in FILES:
        blk, _ = walk(dat[fn], BEST[fn])
        d = defaultdict(list)
        for (off, t, l, p, e) in blk:
            if e is None and p is not None:
                d[t].append((off, p))
        per[fn] = d
    alltags = set()
    for fn in FILES:
        alltags |= set(per[fn].keys())

    w('| TAG | 出现文件数 | 各文件长度 | 各文件均值范围 | 一致性 |')
    w('|---|---|---|---|---|')
    consistent = []
    for t in sorted(alltags):
        fs = [fn for fn in FILES if t in per.get(fn, {})]
        if len(fs) < 2:
            continue
        lens, rngs = [], []
        for fn in fs:
            pays = [p for (_, p) in per[fn][t]]
            lens.append('%s:%s' % (fn[:4], '/'.join(str(len(p)) for p in pays[:2])))
            allb = b''.join(pays)
            if allb:
                rngs.append('%s:%d-%d' % (fn[:4], min(allb), max(allb)))
        # 一致性判定：长度集合是否相交
        lensets = [set(len(p) for (_, p) in per[fn][t]) for fn in fs]
        inter = set.intersection(*lensets) if lensets else set()
        ok = '✅ 长度相交' if inter else '⚠️ 长度全不同'
        if inter:
            consistent.append(t)
        w('| `0x%02X` | %d | %s | %s | %s |'
          % (t, len(fs), ' · '.join(lens), ' · '.join(rngs), ok))
    w()
    w('**长度一致的跨文件 TAG**：%s'
      % (', '.join('`0x%02X`' % t for t in consistent) if consistent else '（无）'))

    txt = '\n'.join(L)
    open(os.path.join(OUT, 'tag_validate.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'T1': t1, 'consistent_tags': ['%02X' % t for t in consistent]},
              open(os.path.join(OUT, 'tag_validate.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    w()
    w('写入：cfg_parsed/tag_validate.txt · tag_validate.json')


main()
