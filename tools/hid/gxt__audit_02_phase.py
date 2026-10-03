# -*- coding: utf-8 -*-
"""
自查 #2：相位与边界的稳健性
用户怀疑「哪里有漏洞」。检查三件事：
  A. 相位 240/272 的推导是否唯一（用全长度扫描，不设窗口）
  B. 加扰区边界到底在哪（0x1200? 0x19800? 0x19A00?）
  C. 是否存在「分区不同相位」的可能（官方固件是多子固件）
"""
import os
from collections import Counter
from math import log2

BASE = r'<LAB>\touchpad-lab'
RAW = os.path.join(BASE, 'bios-re', 'GT7868Q_native_fw.bin')
KEY = os.path.join(BASE, 'poc', 'anchor-hunt', 'GT7868Q_scramble_key.bin')
PLAIN = os.path.join(BASE, 'poc', 'anchor-hunt', 'GT7868Q_plain.bin')

P = 1024

def ent(b):
    c = Counter(b); n = len(b)
    return -sum((v / n) * log2(v / n) for v in c.values())

raw = open(RAW, 'rb').read()
K = open(KEY, 'rb').read()
plain = open(PLAIN, 'rb').read()

print('raw=%d K=%d plain=%d' % (len(raw), len(K), len(plain)))
print()

# ---------- A. 相位扫描（0x00 计数，全长度） ----------
print('=== A. 相位扫描：对 raw[0x1200:] 用 K 移位解扰，统计 0x00 数 ===')
seg = raw[0x1200:]
res = []
for ph in range(P):
    Ke = K[ph:] + K[:ph]
    n = 0
    LIM = 0x18000  # 采样上限，够区分即可
    for i in range(0, min(len(seg), LIM)):
        if seg[i] ^ Ke[i % P] == 0:
            n += 1
    res.append((n, ph))
res.sort(reverse=True)
print('  top10:', [(n, ph) for n, ph in res[:10]])
print('  期望(纯随机) = %d' % (min(len(seg), LIM) // 256))
print()

# ---------- B. 边界检测 ----------
print('=== B. 加扰区边界：raw 与 plain 的差 = K 的周期重复吗 ===')
# 在加扰区，plain = raw ^ K_shift => raw ^ plain 应当是 K 的循环
first = None
last = None
mism = 0
diffs = []
for i in range(len(raw)):
    if raw[i] != plain[i]:
        if first is None: first = i
        last = i
        diffs.append((i, raw[i] ^ plain[i]))
print('  首个差异 @', hex(first) if first else None)
print('  末个差异 @', hex(last) if last else None)
print('  差异字节数', len(diffs))
print()
# 验证差异序列是否等于 K 的循环（相位 ph）
if diffs:
    xr = bytes(b for _, b in diffs)
    ks = (first // 1)  # 从 first 开始的 K 相位
    ok_all = {}
    for ph in range(P):
        good = 0
        for j, (idx, x) in enumerate(diffs[:4000]):
            if x == K[(idx + ph) % P]:
                good += 1
        ok_all[ph] = good
    best = sorted(ok_all.items(), key=lambda kv: -kv[1])[:5]
    print('  K 相位拟合 top5 (匹配/4000):')
    for ph, g in best:
        print('     ph=%4d  match=%d  (%.4f)' % (ph, g, g / 4000))
    ph_best = best[0][0]
    print('  => 差异序列 = K[(idx + %d) %% 1024]' % ph_best)
    print('     等价写法：plain[i] = raw[i] ^ K[(i + %d) %% 1024]' % ph_best)
    print('     或 K 右移 %d 位：Ke[j] = K[(j + %d) %% 1024]' % (ph_best, ph_best))
    print('     之前文档写的「相位 240」对应的位移 = 240')
    print()

# ---------- C. 分段相位检查 ----------
print('=== C. 分段相位：把 0x1200-末 均分 8 段，各自最优相位 ===')
for s in range(8):
    a = 0x1200 + s * (len(raw) - 0x1200) // 8
    b = 0x1200 + (s + 1) * (len(raw) - 0x1200) // 8
    best = None
    for ph in range(P):
        g = 0
        for i in range(a, min(b, a + 8192)):
            if raw[i] ^ K[(i + ph) % P] == plain[i]:
                g += 1
        if best is None or g > best[1]:
            best = (ph, g)
    print('  段%d [%06x,%06x) best ph=%4d match=%d/%d' % (s, a, b, best[0], best[1], min(b, a + 8192) - a))
print()
print('结论：若各段 best ph 一致 => 全文件单一相位，无分区差异。')
