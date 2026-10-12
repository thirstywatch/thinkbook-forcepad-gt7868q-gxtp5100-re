#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lab__r45_diff_structure.py — 判定"差异"是【归零模式】还是【随机版本差异】
（注意：Python 字符串里不要出现中文引号）"""
import re, os, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, '..', '..', 'data', 'logs')


def parse_snap(p):
    m = {}
    for ln in open(p, encoding='utf-8', errors='replace'):
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        mm = re.match(r'^0x([0-9A-Fa-f]{4})\s+(.+)$', ln)
        if not mm:
            continue
        a = int(mm.group(1), 16)
        for i, b in enumerate(bytes(int(x, 16) for x in mm.group(2).split())):
            m[a + i] = b
    return m


A = parse_snap(os.path.join(LOGS, 'lab__snapA.txt'))
B = parse_snap(os.path.join(LOGS, 'lab__snapB.txt'))
d = open(os.path.join(LOGS, 'gxt__degraded_state_v2_20261011.bin'), 'rb').read()
fail = set(json.load(open(os.path.join(LOGS, 'gxt__degraded_failmap.json')))['bad'])
BASE = 0x4000

to_zero = 0; from_zero = 0; other = 0; tot = 0
xor_hist = collections.Counter()
zs = []
os_ = []
for off in range(0, len(d), 256):
    a = BASE + off
    if any((a + k) in fail for k in range(0, 256, 64)):
        continue
    if a + 255 not in A or a + 255 not in B:
        continue
    if any(A[a + i] != B[a + i] for i in range(256)):
        continue
    if b'\xEE' * 16 in d[off:off + 256]:
        continue
    for i in range(256):
        va = A[a + i]; vd = d[off + i]
        if va == vd:
            continue
        tot += 1
        xor_hist[va ^ vd] += 1
        if vd == 0:
            to_zero += 1; zs.append((a + i, va))
        elif va == 0:
            from_zero += 1
        else:
            other += 1; os_.append((a + i, va, vd))

print("=== diff 结构统计（总数 %d）===" % tot)
print("  -> 00 (被清零)   %5d  (%.1f%%)" % (to_zero, to_zero / tot * 100))
print("  00 -> 非零       %5d  (%.1f%%)" % (from_zero, from_zero / tot * 100))
print("  非零 -> 非零     %5d  (%.1f%%)" % (other, other / tot * 100))
print()
print("=== XOR 值分布 top 12 ===")
for v, c in xor_hist.most_common(12):
    print("   XOR=0x%02X  %4d 次  (%.1f%%)" % (v, c, c / tot * 100))
onebit = sum(c for v, c in xor_hist.items() if bin(v).count('1') == 1)
print()
print("  单比特差异: %d (%.1f%%)" % (onebit, onebit / tot * 100))
print("  判定: %s" % ("接近随机（无显著位模式）=> 支持[版本差异]"
                   if onebit / tot < 0.2 else "有明显位翻转 => 支持[系统性改动]"))
print()
print("=== 全零 256B 块计数 ===")
zc = 0
for off in range(0, len(d), 256):
    a = BASE + off
    if any((a + k) in fail for k in range(0, 256, 64)):
        continue
    if all(x == 0 for x in d[off:off + 256]):
        zc += 1
zcA = 0
for off in range(0, 0x6000, 256):
    a = BASE + off
    if a + 255 in A and all(A[a + i] == 0 for i in range(256)):
        zcA += 1
print("  退化态全零 256B 块: %d" % zc)
print("  正常态全零 256B 块: %d" % zcA)
print()
print("=== 被清零的字节的位置分布（top 20 连续段）===")
if zs:
    zs.sort()
    runs = []
    st = zs[0][0]; pv = zs[0][0]; items = [zs[0]]
    for x in zs[1:]:
        if x[0] == pv + 1:
            pv = x[0]; items.append(x)
        else:
            runs.append((st, pv, items)); st = x[0]; pv = x[0]; items = [x]
    runs.append((st, pv, items))
    for s, e, it in sorted(runs, key=lambda r: -(r[1] - r[0]))[:20]:
        print("  0x%04X-0x%04X (%3d B)  原值: %s"
              % (s, e, e - s + 1, " ".join("%02X" % v for _, v in it[:8])))
    print()
    print("  被清零字节总数 %d ；连续段 %d" % (len(zs), len(runs)))
