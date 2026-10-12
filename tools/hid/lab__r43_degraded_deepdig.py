#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r43_degraded_deepdig.py — 退化态深挖（全静态区 A/B + 压力帧族检查）

★ 原则
  · 只对【正常态两次快照一致】的区段做 diff（否则是易变数据，diff 无意义）—— 纪律 141
  · 全程只读
"""
import re, os

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
d = open(os.path.join(LOGS, 'gxt__degraded_state_20261011.bin'), 'rb').read()
BASE = 0x4000
print("退化态 dump: %d B (0x%04X-0x%04X)" % (len(d), BASE, BASE + len(d)))

# ── 1) 找出所有【正常态稳定】的 256 B 块 ──
print()
print("=" * 78)
print("① 全静态区 A/B（只对这些块做 diff）")
print("=" * 78)
stable = []
for off in range(0, 0x6000, 256):
    a = BASE + off
    if a + 255 not in A or a + 255 not in B:
        continue
    if all(A[a + i] == B[a + i] for i in range(256)):
        stable.append(a)
print("正常态稳定块数: %d / %d" % (len(stable), 0x6000 // 256))

runs = []
if stable:
    st = stable[0]; pv = stable[0]
    for x in stable[1:]:
        if x == pv + 256:
            pv = x
        else:
            runs.append((st, pv)); st = x; pv = x
    runs.append((st, pv))

print()
print("  %-20s %-8s %-10s %s" % ("静态区段", "大小", "退化态差异", "差异字节示例"))
total_diff = 0
for s, e in runs:
    n = 0; sample = []
    for a in range(s, e + 256):
        vd = d[a - BASE]
        if vd != A[a]:
            n += 1
            if len(sample) < 5:
                sample.append("0x%04X:%02X->%02X" % (a, A[a], vd))
    total_diff += n
    print("  0x%04X-0x%04X  %5d B  %4d (%5.1f%%)  %s"
          % (s, e + 256, e + 256 - s, n, n / (e + 256 - s) * 100, " ".join(sample)))
print()
print("静态区总差异: %d 字节" % total_diff)

# ── 2) 压力帧族专项 ──
print()
print("=" * 78)
print("② 压力帧族 0x5F00 专项（项目已标定 0x5F20/0x5F21 = 按压状态）")
print("=" * 78)
for a in range(0x5F00, 0x5F60, 16):
    va = " ".join("%02X" % A[a + i] for i in range(16) if a + i in A)
    vb = " ".join("%02X" % B[a + i] for i in range(16) if a + i in B)
    vd = d[a - BASE:a - BASE + 16].hex(' ').upper()
    flag = "  ★差异" if va != vd else ""
    print("  0x%04X  snapA: %-47s  退化: %s%s" % (a, va, vd, flag))

print()
print("  ★ 关键：0x5F20/0x5F21（项目标的'按压状态'）")
for a in (0x5F20, 0x5F21, 0x5F24):
    va = A.get(a); vb = B.get(a); vd = d[a - BASE]
    print("    0x%04X  snapA=%02X snapB=%02X  退化=%02X   %s"
          % (a, va if va is not None else 0, vb if vb is not None else 0, vd,
             ("★稳定区且退化不同" if va == vb and va != vd else
              ("正常态两快照一致" if va == vb else "⚠️正常态就在变"))))

# ── 3) 5F00 族的"帧头"是否还在 ──
print()
print("③ 压力帧头 7F 10 80 00 00 00 00 3C 在退化态中是否出现")
for tag, pat in [("0x5F00 帧头", bytes.fromhex("7F1080000000003C")),
                 ("0x5600 帧头", bytes.fromhex("0001010201051834")),
                 ("0x5900 帧头", bytes.fromhex("7F107F88"))]:
    hits = []
    for a in range(0x4000, 0x9F00):
        if a - BASE + len(pat) > len(d):
            break
        if d[a - BASE:a - BASE + len(pat)] == pat:
            hits.append(hex(a))
    hitsA = [a for a in range(0x4000, 0x9F00) if all(A.get(a + i) == pat[i] for i in range(len(pat)))]
    print("  %-12s 退化态: %-28s 正常态(snapA): %s"
          % (tag, hits[:5] if hits else "无", [hex(x) for x in hitsA[:5]] if hitsA else "无"))
