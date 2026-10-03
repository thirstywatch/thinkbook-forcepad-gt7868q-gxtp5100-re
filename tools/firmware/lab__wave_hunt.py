#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
波形库猎手 —— AW86927 的波形库正好是 8 KB SRAM（§19.15）
若 GT7868Q 用 RAM 模式驱动它，固件里必须存在 8 KB 波形数组 ⇒ 载荷A 里那些 8192 B 的
type-3 块是首选候选。

★ 修正一个会产出假结论的 bug（本脚本第一版就踩了）：
  块必须按【数据区顺序连续切分】，每块内相位从 0 起算（= 数据区相对 572）。
  若循环里对每块都写 `base:base+size`（不推进 off），就会把同一段raw 重复解 8 次
  ⇒ 8 个块 md5 全同 → 误以为"它们是同一份数据"。
  正确：off += size 累进。相位基准 A/B 都对（结果相同，因为 1024 | 各块长）。

判据（不靠猜，靠数据形态）：
  W1 幅度是小的有符号整数（|v| 远小于 128），不是均匀分布 0..255
  W2 相邻样本有局部平滑性（自相关显著），不是白噪声
  W3 幅度包络：波形头尾幅度不同（起振/衰减）
  W4 若为多段波形，应能找到重复的波形块（同一段数据在flash 里出现多次）
"""
import sys, os, math, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decrypt import find_container, parse_container, DATA_OFF

K = open(r'..\anchor-hunt\GT7868Q_scramble_key.bin','rb').read()
FW = r'..\..\bios-re\GT7868Q_native_fw.bin'
DATA_PHASE = 572      # 数据区相对相位 = 316 + 0x100


def entropy(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())


def autocorrelation(b, lag):
    """归一化自相关；白噪声 ~0，周期信号在对应 lag 处显著"""
    n = len(b)
    if n <= lag + 1: return 0.0
    m = sum(b)/n
    num = sum((b[i]-m)*(b[i+lag]-m) for i in range(n-lag))
    den = sum((x-m)**2 for x in b)
    return num/den if den else 0.0


def longest_zero_run(b):
    best = cur = 0
    for x in b:
        cur = cur+1 if x == 0 else 0
        best = max(best, cur)
    return best


def main():
    buf = open(FW,'rb').read()
    o = find_container(buf); info = parse_container(buf, o)
    base = o + DATA_OFF

    print('='*118)
    print('载荷A 各块形态分析（相位 = 数据区相对 572，连续切分）')
    print('='*118)
    print('idx flash    size   type  H0      零%最长0串 | 幅值域(有符号8bit)  |[-8,7]占比 |AC(1)  AC(16)')
    print('-'*118)

    blocks = []
    off = 0
    for s in info['subsys']:
        raw = buf[base+off: base+off+s['size']]
        pl = bytes(v ^ K[(i + DATA_PHASE) % 1024] for i, v in enumerate(raw))
        blocks.append((s, pl))
        off += s['size']

    for s, pl in blocks:
        n = len(pl)
        h0 = entropy(pl)
        zr = pl.count(0)*100.0/n
        lz = longest_zero_run(pl)
        s8 = [(b-256 if b >= 128 else b) for b in pl]
        lo, hi = min(s8), max(s8)
        small = sum(1 for v in s8 if -8 <= v <= 7)*100.0/n
        ac1 = autocorrelation(s8, 1)
        ac16 = autocorrelation(s8, 16)
        print('%3d 0x%05X %6d  0x%02X  %.3f %5.1f %6d  | %4d..%4d          | %5.1f%%  | %+.3f %+.3f'
              % (s['idx'], s['flash_addr'], n, s['type'], h0, zr, lz, lo, hi, small, ac1, ac16))

    # 白噪声对照：同长度真随机
    import random
    rnd = bytes(random.randrange(256) for _ in range(8192))
    s8r = [(b-256 if b>=128 else b) for b in rnd]
    print()
    print('对照（同长真随机）: H0=%.3f  |[-8,7]占比=%.1f%%  AC(1)=%+.3f  AC(16)=%+.3f'
          % (entropy(rnd), sum(1 for v in s8r if -8<=v<=7)*100.0/8192,
             autocorrelation(s8r,1), autocorrelation(s8r,16)))

    # 重复块检测（多段波形的关键特征）
    print()
    print('★ 全载荷A 内的重复子串（找"多段波形"）：')
    seen = collections.defaultdict(list)
    for s, pl in blocks:
        seen[hashlib.md5(pl).hexdigest()].append(('blk%d@0x%05X' % (s['idx'], s['flash_addr'])))
    for h, locs in seen.items():
        if len(locs) > 1:
            print('  整块重复:', h[:10], locs)
    # 512 B 粒度的重复
    reps = collections.defaultdict(set)
    for s, pl in blocks:
        for i in range(0, len(pl)-512, 512):
            reps[hashlib.md5(pl[i:i+512]).hexdigest()].add('%d:%05X' % (s['idx'], i))
    multi = {h:v for h,v in reps.items() if len(v) > 1}
    print('  512B 粒度重复块数: %d （若>0 且分布成组 ⇒ 疑似多段波形表）' % len(multi))
    for h, v in list(multi.items())[:6]:
        print('    %s x%d : %s' % (h[:10], len(v), sorted(v)[:8]))


if __name__ == '__main__':
    main()
