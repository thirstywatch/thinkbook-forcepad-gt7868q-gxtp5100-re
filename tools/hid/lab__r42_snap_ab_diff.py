#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三方对照：snapA(正常) vs snapB(正常) vs 退化态 —— 只对静态信息区 0x4000-0x4400"""
import re, os, sys

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
dp = os.path.join(LOGS, 'gxt__degraded_state_20261011.bin')
d = open(dp, 'rb').read()
BASE = 0x4000

print("=== 逐 256 B 块：snapA vs snapB（正常态自一致性）—— 看哪些段是【静态】的 ===")
stable_ranges = []
for off in range(0, 0x6000, 256):
    a = BASE + off
    if a + 255 not in A or a + 255 not in B:
        continue
    n = sum(1 for i in range(256) if A[a + i] != B[a + i])
    tag = "★静态" if n == 0 else ""
    if off < 0x400 or n == 0:
        print("  0x%04X  snapA-vs-snapB 差异 %3d/256  %s" % (a, n, tag))
    if n == 0:
        stable_ranges.append(a)

print()
print("=== 静态段汇总（snapA==snapB 的 256B 块）===")
if stable_ranges:
    runs = []
    st = stable_ranges[0]; pv = stable_ranges[0]
    for x in stable_ranges[1:]:
        if x == pv + 256:
            pv = x
        else:
            runs.append((st, pv)); st = x; pv = x
    runs.append((st, pv))
    for s, e in runs:
        print("  0x%04X - 0x%04X  (%d B)" % (s, e + 256, e + 256 - s))
else:
    print("  无 —— 整个区域都是易变的")

print()
print("=== 0x4000-0x4080 三方逐字节对照 ===")
print("  addr    snapA  snapB  退化态 | 判定")
for a in range(0x4000, 0x4080):
    va = A.get(a); vb = B.get(a); vd = d[a - BASE] if a - BASE < len(d) else None
    if va is None or vb is None:
        continue
    if va == vb:
        mark = "正常态稳定"
        extra = ("  ★退化态不同 %02X→%02X" % (va, vd)) if va != vd else ""
    else:
        mark = "正常态就在变"
        extra = ""
    print("  0x%04X   %02X     %02X     %02X    | %s%s"
          % (a, va, vb, vd, mark, extra))

print()
print("=== 只在【正常态两快照一致的字节】上统计退化态差异 ===")
stable_same = 0; stable_tot = 0; changed = []
for a in range(0x4000, 0x4400):
    va = A.get(a); vb = B.get(a)
    if va is None or vb is None:
        continue
    stable_tot += 1
    if va == vb:
        stable_same += 1
        vd = d[a - BASE] if a - BASE < len(d) else None
        if vd is not None and va != vd:
            changed.append((a, va, vd))
print("  0x4000-0x43FF：正常态两快照一致 %d/%d = %.1f%%" % (stable_same, stable_tot, stable_same / stable_tot * 100))
print("  其中【退化态与之不同】的字节数: %d" % len(changed))
print()
if changed:
    runs = []
    st = changed[0][0]; pv = changed[0][0]
    for a, _, _ in changed[1:]:
        if a == pv + 1:
            pv = a
        else:
            runs.append((st, pv)); st = a; pv = a
    runs.append((st, pv))
    print("  连续段（共 %d 段）:" % len(runs))
    for s, e in runs[:30]:
        print("    0x%04X-0x%04X (%d B)   %s"
              % (s, e, e - s + 1,
                 " ".join("%02X→%02X" % (v, w) for aa, v, w in changed if s <= aa <= min(e, s + 5))))
