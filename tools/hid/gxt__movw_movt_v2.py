# -*- coding: utf-8 -*-
# 第十九轮 G：MOVW/MOVT 全局配对（滑动扫描，不顺序解码）
# 修正上一版的错误：顺序解码在遇到不可识别半字时步进错误，导致配对全丢。
# 正确做法：对每个偶数偏移尝试作为 MOVW，然后在 +2/+4/+6/+8 处找同寄存器 MOVT。
# 验证手段（关键）：配对出的 32 位值必须落在【已知合法段】才算真配对。
import struct, os
from collections import Counter, defaultdict

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

w("="*78)
w("MOVW/MOVT 全局配对（第十九轮 G）")
w("="*78)

def dec(off):
    if off + 4 > len(D): return None
    hw1 = D[off] | (D[off+1] << 8)
    hw2 = D[off+2] | (D[off+3] << 8)
    if (hw1 >> 11) != 0b11110: return None
    op = hw1 & 0x0FF0
    if op not in (0x240, 0x2C0): return None
    i = (hw1 >> 10) & 1
    imm4 = hw1 & 0xF
    imm3 = (hw2 >> 12) & 0x7
    rd = (hw2 >> 8) & 0xF
    imm8 = hw2 & 0xFF
    imm16 = (imm4 << 12) | (i << 11) | (imm3 << 8) | imm8
    return ('MOVW' if op == 0x240 else 'MOVT'), rd, imm16

# ---------- 自检：用已知样本 ----------
w()
w("### 0. 解码器自检（已知样本）")
for off in [0x1E018, 0x1E01C, 0x1E028, 0x1E040, 0x1E044]:
    w("    0x%05X  %s" % (off, dec(off)))

# ---------- 1. 滑动配对 ----------
w()
w("### 1. 滑动配对：MOVW 在 off，MOVT 在 off+2..off+12 内且同 Rd")
def pair_scan(lo, hi):
    movw = {}
    movt = {}
    for off in range(lo & ~1, hi - 3, 2):
        r = dec(off)
        if not r: continue
        k, rd, imm = r
        if k == 'MOVW': movw[off] = (rd, imm)
        else: movt[off] = (rd, imm)
    pairs = []
    for o1, (r1, i1) in movw.items():
        for d in (2, 4, 6, 8, 10, 12):
            o2 = o1 + d
            if o2 in movt and movt[o2][0] == r1:
                i2 = movt[o2][1]
                pairs.append((o1, r1, (i2 << 16) | i1, i1, i2, d))
                break
    return pairs, movw, movt

allpairs = []
for lo, hi, nm in [(0x00000, 0x20000, '0x00000-0x20000'),
                   (0x20000, len(D), '0x20000-END')]:
    p, mw, mt = pair_scan(lo, hi)
    w()
    w("  --- %s ---" % nm)
    w("    MOVW 命中 %d 条, MOVT 命中 %d 条, 配对 %d 组" % (len(mw), len(mt), len(p)))
    allpairs += p
    # 列出前 30 组
    for o1, rd, addr, i1, i2, d in p[:30]:
        w("      0x%05X  R%-2d = 0x%08X   (lo=0x%04X hi=0x%04X  gap=%d)" % (o1, rd, addr, i1, i2, d))

# ---------- 2. 合理性过滤 ----------
w()
w("### 2. ★合理性过滤：只有落在已知地址段的算真地址")
legal = {'Flash 0x08000000-0x081FFFFF': (0x08000000, 0x08200000),
         'SRAM 0x20000000-0x2001FFFF': (0x20000000, 0x20020000),
         '外设 0x40000000-0x5FFFFFFF': (0x40000000, 0x60000000),
         '系统 0xE0000000-0xE00FFFFF': (0xE0000000, 0xE0100000)}
cnt = Counter()
good = []
for o1, rd, addr, i1, i2, d in allpairs:
    for nm, (lo, hi) in legal.items():
        if lo <= addr < hi:
            cnt[nm] += 1
            good.append((o1, rd, addr, nm))
            break
    else:
        cnt['★非法(非地址)'] += 1
w()
for nm, n in cnt.most_common():
    w("    %-32s %d" % (nm, n))
w()
w("  -> 合法占比 %.3f" % (sum(v for k, v in cnt.items() if not k.startswith('★')) / max(1, len(allpairs))))

w()
w("### 3. ★合法地址明细")
c = Counter(a for _, _, a, _ in good)
for a, n in sorted(c.items()):
    nm = [k for k, (lo, hi) in legal.items() if lo <= a < hi][0]
    w("    0x%08X  x%-3d  %s" % (a, n, nm))

# ---------- 4. 每组配对的 gap 分布 ----------
w()
w("### 4. MOVW→MOVT 间隔 gap 分布")
w("    %s" % str(Counter(d for _, _, _, _, _, d in allpairs).most_common()))

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed', 'movw_movt_v2.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
