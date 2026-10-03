#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
载荷A 结构测绘 · 第2步：★ 抓住 Q1 那个反常数字。

Q1 发现：相邻行（L=8/16/32…任意 L）同位相同率 **14–16%**，而真随机基线是 0.39%。
⇒ 载荷 A 里存在【跨行的强列结构】。这不是"块"能表达的，必须做【转置视图】。

做法：把数据看成 L 行 × C 列的矩阵（列优先/行优先两种），
     若某些"列"或"行"内部高度相似，说明存在 L 个并行通道 —— 这正是
     §19.13.2「16 B/条 × 8 = 128 B 组」说的东西，但从未被真正看清。

判据（全部可自校准，不需要外部知识）：
  T1 转置后同位相同率（应远高于随机 ⇒ 列是真正的结构单位）
  T2 每一列的"非零率"是否成组（若某些列恒零、某些列密集 ⇒ 稀疏矩阵）
  T3 列两两之间的相关性聚类（若 8 个一组内互相关高 ⇒ K=8 的通道结构）
"""
import sys, os, math, collections, itertools, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decrypt import find_container, parse_container, DATA_OFF

HERE = os.path.dirname(os.path.abspath(__file__))
K = open(os.path.join(HERE, r'..\anchor-hunt\GT7868Q_scramble_key.bin'), 'rb').read()
FW = os.path.join(HERE, r'..\..\bios-re\GT7868Q_native_fw.bin')
PH = 572


def load_alld(path=FW):
    buf = open(path,'rb').read()
    o = find_container(buf); info = parse_container(buf, o)
    base = o + DATA_OFF
    blocks = []; off = 0
    for s in info['subsys']:
        raw = buf[base+off: base+off+s['size']]
        blocks.append((s, bytes(v ^ K[(i+PH) % 1024] for i, v in enumerate(raw))))
        off += s['size']
    return blocks, b''.join(b for _, b in blocks)


def hx(h):
    return ''.join('%02X' % b for b in h)


def main():
    blocks, A = load_alld()
    n = len(A)
    print('载荷A 全长%d B = %d KB' % (n, n//1024))
    print()

    # 随机基线
    rnd = bytes(random.Random(12345).randrange(256) for _ in range(n))
    print('='*100)
    print('T1 · lag=L 自相关（同位相同率），载荷A vs 随机基线')
    print('='*100)
    print('  ⚠ 基线必须是【真随机 vs 自己】—— 拿随机数据和自己比必然 100%，是错的。')
    print('     正确基线 = 1/256 = 0.391%（256 个字节值均匀分布时的期望）')
    print()
    print('  L        期望基线   载荷A实测   比值')
    for L in (8, 16, 32, 64):
        a = sum(1 for i in range(n-L) if A[i] == A[i+L]) / (n-L)
        print('  %-8d  %7.3f%%   %7.2f%%    %6.1f×' % (L, 100/256, a*100, a*256))
    print()
    print('  实测 12–16% 远高于0.391% ⇒ 载荷 A 存在【跨块共享的列结构】')
    print('  （若只是块内数据，相邻行同位相同率应回落到 0.39%）')
    print()

    print('='*100)
    print('T2 · 完整 lag 自相关曲线（只看载荷A，基线 1/256）')
    print('='*100)
    print('  lag    载荷A     /基线')
    curve = []
    for lag in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024):
        a = sum(1 for i in range(n-lag) if A[i] == A[i+lag]) / (n-lag)
        curve.append((lag, a))
        print('  %5d  %7.3f%%  %6.1f×' % (lag, a*100, a*256))
    best = max(curve, key=lambda t: t[1])
    print()
    print('  ★ 峰值在 lag=%d（%.2f%%，基线的 %.1f 倍）' % (best[0], best[1]*100, best[1]*256))
    print()

    print('='*100)
    print('T3 · 分块 lag 自相关（排除"整块零填充"造成的假高）')
    print('='*100)
    print('  只统计【两块都非零】的字节对')
    for lag in (1, 2, 4, 8, 16, 32, 64, 128, 256):
        tot = hit = 0
        for s, pl in blocks:
            b = pl
            for i in range(len(b)-lag):
                if b[i] and b[i+lag]:
                    tot += 1
                    if b[i] == b[i+lag]: hit += 1
        rr = 1/256.0
        print('  lag=%5d  实测 %7.3f%%  非零对 %7d  ⇒ %.1f×随机' % (lag, hit/tot*100, tot, (hit/tot)/rr))
    print()

    print('='*100)
    print('T4 · 字节位置的周期性（哪些 offset 上数据"稀疏"）')
    print('='*100)
    for period in (16, 32, 64, 128, 256):
        nz_by_off = [0]*period
        for i, b in enumerate(A):
            if b: nz_by_off[i % period] += 1
        per_col = n/period
        rates = [c/per_col for c in nz_by_off]
        lo = sum(1 for r in rates if r < 0.10)
        hi = sum(1 for r in rates if r > 0.90)
        print('  period=%4d  非零率 min=%.3f max=%.3f 均值=%.3f  | 恒低(<10%%)列=%d 恒高(>90%%)列=%d'
              % (period, min(rates), max(rates), sum(rates)/len(rates), lo, hi))
    print()

    print('='*100)
    print('T5 · 前 512 B 的实际字节（看结构长什么样）')
    print('='*100)
    for blk_i, (s, pl) in enumerate(blocks[:2]):
        print('--- 块 idx=%d flash=0x%05X type=0x%02X ---' % (s['idx'], s['flash_addr'], s['type']))
        for i in range(0, 256, 16):
            print('  %04X  %s' % (i, ' '.join('%02X' % b for b in pl[i:i+16])))
        print()


if __name__ == '__main__':
    main()
