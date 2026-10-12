#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lab__r52_corrected_snap_compare.py — ★ 用【正确的字节序】重做 snapA 对比

发现：lab__snapA/B.txt 快照是【4 字节一组反转】存储的
  证据1：snapA 0x4000 = B1 ED E0 A7 CC CC 9D F4，反转后 = A7 E0 ED B1 F4 9D CC DC
         = 《全书》§19.34.2 记录值，逐字节一致
  证据2：snapA 0x4018 = 53 4C 45 59，反转后 = 59 45 4C 53 = "YELS"，与当前设备一致
（Python 字符串里不要出现中文引号）"""
import re, os

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, '..', '..', 'data', 'logs')


def parse_snap_rev(p):
    """解析快照，并做 4 字节组内反转"""
    m = {}
    for ln in open(p, encoding='utf-8', errors='replace'):
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        mm = re.match(r'^0x([0-9A-Fa-f]{4})\s+(.+)$', ln)
        if not mm:
            continue
        a = int(mm.group(1), 16)
        bs = bytes(int(x, 16) for x in mm.group(2).split())
        for i, b in enumerate(bs):
            m[a + i] = b
    # 反转：每 4 字节一组
    out = {}
    base = min(m)
    hi = max(m)
    for a in range(base, hi + 1):
        if a in m:
            g = a - (a % 4)
            out[a] = m.get(g + (3 - (a % 4)), m[a])
    return out


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


RAW = parse_snap(os.path.join(LOGS, 'lab__snapA.txt'))
RAWB = parse_snap(os.path.join(LOGS, 'lab__snapB.txt'))
A = parse_snap_rev(os.path.join(LOGS, 'lab__snapA.txt'))
B = parse_snap_rev(os.path.join(LOGS, 'lab__snapB.txt'))
low = open(os.path.join(LOGS, 'gxt__now_low_20261011.bin'), 'rb').read()
high = open(os.path.join(LOGS, 'gxt__now_high_20261011.bin'), 'rb').read()


def cur(a):
    return low[a] if a < 0x4000 else high[a - 0x4000]


print("=== 验证：反转是否正确 ===")
print("  snapA 原始 0x4000: %s" % " ".join("%02X" % RAW[0x4000 + i] for i in range(8)))
print("  snapA 反转 0x4000: %s" % " ".join("%02X" % A[0x4000 + i] for i in range(8)))
print("  《全书》记录      : A7 E0 ED B1 F4 9D CC DC")
print("  当前设备          : %s" % " ".join("%02X" % cur(0x4000 + i) for i in range(8)))
print()
print("  snapA 反转 0x4018: %s  (ASCII: %r)"
      % (" ".join("%02X" % A[0x4018 + i] for i in range(6)),
         bytes(A[0x4018 + i] for i in range(6))))
print()

# 反转后 正常态两快照一致性
common = [a for a in A if a in B]
same = sum(1 for a in common if A[a] == B[a])
print("  反转后 snapA vs snapB 相同率: %.2f%%  (反转前 %.2f%%)"
      % (same / len(common) * 100,
         sum(1 for a in common if RAW[a] == RAWB[a]) / len(common) * 100))
print()

print("=" * 78)
print("=== ★ 反转后：正常态 vs 当前(退化态)，找 【正常非零 -> 当前为 0】 的候选 ===")
print("=" * 78)
off_sig = []
for a in range(0x0000, 0x9F00):
    if a not in A or a not in B:
        continue
    if A[a] != B[a]:
        continue          # 只取正常态稳定的字节
    if A[a] != 0 and cur(a) == 0:
        off_sig.append((a, A[a]))
print("  候选字节数（正常非零 -> 当前 0）: %d" % len(off_sig))
if off_sig:
    runs = []
    st = off_sig[0][0]; pv = off_sig[0][0]; it = [off_sig[0]]
    for x in off_sig[1:]:
        if x[0] == pv + 1:
            pv = x[0]; it.append(x)
        else:
            runs.append((st, pv, it)); st = x[0]; pv = x[0]; it = [x]
    runs.append((st, pv, it))
    print("  连续段（top 30，按长度）:")
    for s, e, ii in sorted(runs, key=lambda r: -(r[1] - r[0]))[:30]:
        print("    0x%04X-0x%04X (%3d B)  正常值: %s"
              % (s, e, e - s + 1, " ".join("%02X" % v for _, v in ii[:12])))

print()
print("=== 关键区：反转后 正常 vs 当前 ===")
for base, ln, nm in [(0x1800, 0x20, '0x1800 触觉参数区'),
                     (0x3800, 0x20, '0x3800 触觉参数区'),
                     (0x1C00, 0x40, '0x1C00 可写区')]:
    print("  ── %s ──" % nm)
    for i in range(0, ln, 8):
        va = " ".join("%02X" % A.get(base + i + j, 0) for j in range(8))
        vc = " ".join("%02X" % cur(base + i + j) for j in range(8))
        mark = "  ★" if va != vc else ""
        print("    0x%04X  正常 %-23s  当前 %s%s" % (base + i, va, vc, mark))
