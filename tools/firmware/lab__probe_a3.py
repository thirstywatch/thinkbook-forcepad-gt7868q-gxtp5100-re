#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
载荷A 结构测绘 · 第3步：★ 解决 T1 与 T3 的矛盾。

矛盾：
  T1（全部字节）lag=16 自相关 15.78% = 基线 40×
  T3（只统计两边都非零）lag=16 只有 3.45% = 基线 8.8×
⇒ 自相关的主体来自【零 vs 零】的配对。
  也就是说：**不是"某结构周期性重复"，而是"零成片出现"。**

所以真正要回答的是：
  Z1 零字节在 lag=16 上的配对有多强？（零的空间分布）
  Z2 载荷A 的非零部分（真正的数据）自身有没有结构？
  Z3 载荷A 是不是 "数据 + 大片空白" 的混合？空白占比多少、边界在哪？
  Z4 ★ 关键：把零全部挖掉，剩下的"数据骨架"长什么样？

这是决定性的：如果挖掉零之后骨架呈现规则结构，那载荷 A 是
"稀疏参数表"（值 + 大量未使用槽位）；如果骨架是均匀噪声，那它是"加密过的压缩块"。
"""
import sys, os, math, collections, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decrypt import find_container, parse_container, DATA_OFF

HERE = os.path.dirname(os.path.abspath(__file__))
K = open(os.path.join(HERE, r'..\anchor-hunt\GT7868Q_scramble_key.bin'), 'rb').read()
FW = os.path.join(HERE, r'..\..\bios-re\GT7868Q_native_fw.bin')
PH = 572


def load_blocks(path=FW):
    buf = open(path,'rb').read()
    o = find_container(buf); info = parse_container(buf, o)
    base = o + DATA_OFF
    out = []; off = 0
    for s in info['subsys']:
        raw = buf[base+off: base+off+s['size']]
        out.append((s, bytes(v ^ K[(i+PH) % 1024] for i, v in enumerate(raw))))
        off += s['size']
    return info, out


def entropy(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())


def runs_of(b, val):
    """返回 (起点, 长度) 列表 —— 长度 >= 1 的完整游程"""
    out = []
    i = 0
    n = len(b)
    while i < n:
        if b[i] == val:
            j = i
            while j < n and b[j] == val:
                j += 1
            out.append((i, j - i))
            i = j
        else:
            i += 1
    return out


def main():
    info, blocks = load_blocks()
    A = b''.join(b for _, b in blocks)
    n = len(A)

    print('='*100)
    print('Z1 · 零字节的空间分布')
    print('='*100)
    runs = runs_of(A, 0)
    runs.sort(key=lambda t: -t[1])
    print('  零字节总数 %d (%.2f%%)' % (A.count(0), A.count(0)*100.0/n))
    print('  连续零段数 %d ；最长 10 段:' % len(runs))
    for st, ln in runs[:10]:
        blk = _which(st)
        print('    off=0x%06X len=%6d  (属于 %s)' % (st, ln, blk))
    big = [t for t in runs if t[1] >= 64]
    print('  ≥64 B 的零段 %d 个，合计 %d B (%.1f%% of 全载荷)' % (len(big), sum(l for _, l in big), sum(l for _, l in big)*100.0/n))
    print()

    print('='*100)
    print('Z2 · 分块：零占比 vs 非零部分的熵')
    print('='*100)
    print('  idx flash    type  size   零%    非零部分H0  非零/总字节')
    tot_nz = 0
    for s, pl in blocks:
        nz = bytes(x for x in pl if x)
        tot_nz += len(nz)
        print('  %3d 0x%05X 0x%02X %6d %5.1f%%   %8.3f     %6d'
              % (s['idx'], s['flash_addr'], s['type'], len(pl),
                 pl.count(0)*100.0/len(pl), entropy(nz), len(nz)))
    nzall = bytes(x for x in A if x)
    print('  %3s %s    %s %6d %5.1f%%   %8.3f     %6d' % ('ALL','','', n, A.count(0)*100.0/n, entropy(nzall), len(nzall)))
    print()
    print('  ★ 非零部分的 H0 = %.3f ⇒ %s'
          % (entropy(nzall), '接近 8.0 = 真随机/加密；明显低于 8 = 压缩；接近 6-7 = 结构化数值表'))
    print()

    print('='*100)
    print('Z3 · 把零全部挖掉，看骨架的长度与间隔分布')
    print('='*100)
    idxs = [i for i, x in enumerate(A) if x]
    gaps = collections.Counter()
    for i in range(1, len(idxs)):
        gaps[idxs[i]-idxs[i-1]] += 1
    print('  非零字节数 %d ；相邻非零间距分布 top 12:' % len(idxs))
    for g, c in gaps.most_common(12):
        print('    间距 %4d  x%7d  (%.1f%%)' % (g, c, c*100.0/len(idxs)))
    print()
    print('  游程（连续非零段）分布：')
    nr = runs_of(A, 1)
    nr.sort(key=lambda t: -t[1])
    print('    非零段数 %d ；最长 10 段:' % len(nr))
    for st, ln in nr[:10]:
        print('      off=0x%06X len=%5d' % (st, ln))
    print()

    print('='*100)
    print('Z4 · 骨架的字节值分布（零被挖掉后的 8万字节）')
    print('='*100)
    c = collections.Counter(nzall)
    exp = len(nzall)/256.0
    chi2 = sum((c.get(i,0)-exp)**2/exp for i in range(256))
    print('  卡方(df=255) = %.1f  （255 ≈ 均匀分布；>>255 说明值集中在少数几个）' % chi2)
    print('  最常见 16 个值:')
    tot = len(nzall)
    for v, k in c.most_common(16):
        bar = '#' * int(k*60/tot)
        print('    0x%02X %4d %5.2f%% %s' % (v, k, k*100.0/tot, bar))
    print()
    print('  值 <= 0x10 的占比: %.1f%%   值 >= 0xF0 的占比: %.1f%%'
          % (sum(k for v,k in c.items() if v <= 0x10)*100.0/tot,
             sum(k for v,k in c.items() if v >= 0xF0)*100.0/tot))
    print()

    print('='*100)
    print('Z5 · 按 16 字节切：每条的"零个数"分布（验证 §19.13.2 的16B/条）')
    print('='*100)
    recs = [A[i:i+16] for i in range(0, n-15, 16)]
    zc = collections.Counter(sum(1 for x in r if x == 0) for r in recs)
    print('  16 B 条数 %d ；每条零个数分布:' % len(recs))
    for z, c2 in sorted(zc.items()):
        print('    %2d 零  x%6d  %5.1f%%' % (z, c2, c2*100.0/len(recs)))
    full = zc.get(16, 0)
    print('  全零条 %d (%.1f%%) ⇒ 净数据约 %d B' % (full, full*100.0/len(recs), (len(recs)-full)*16))


def _which(off):
    cum = 0
    return '?'


if __name__ == '__main__':
    main()
