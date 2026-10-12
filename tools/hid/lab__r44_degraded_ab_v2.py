#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r44_degraded_ab_v2.py — 修正版 A/B（★ 排除读失败块）

修正内容（对比 r43 的错误）：
  r43 把【读失败】占位值 0xEE 当成了数据 ⇒ 那些"差异"是假的。
  本脚本：① 用 v2 dump（失败图单独记录）② 三重过滤后**才**做 diff
     过滤 1：该 256 B 块【不在失败图里】
     过滤 2：正常态两次快照（snapA==snapB）该块**逐字节一致**（静态）
     过滤 3：块内**没有 0xEE 长串**（防止其它占位/巧合）
"""
import re, os, json

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
failmap = set(json.load(open(os.path.join(LOGS, 'gxt__degraded_failmap.json')))['bad'])
BASE = 0x4000

print("v2 dump: %d B  失败块 %d 个" % (len(d), len(failmap)))
print()
print("=" * 84)
print("★ 三重过滤后的 A/B（这才是可信的差异）")
print("=" * 84)

rows = []
for off in range(0, len(d), 256):
    a = BASE + off
    # 过滤 1：本块或其相邻是否有读失败
    if any((a + k) in failmap for k in range(0, 256, 64)):
        continue
    # 过滤 2：正常态静态
    if a + 255 not in A or a + 255 not in B:
        continue
    if any(A[a + i] != B[a + i] for i in range(256)):
        continue
    # 过滤 3：块内无 0xEE 长串（>=16 连续）
    w = d[off:off + 256]
    if b'\xEE' * 16 in w:
        continue
    n = 0; sample = []
    for i in range(256):
        if d[off + i] != A[a + i]:
            n += 1
            if len(sample) < 6:
                sample.append("0x%04X:%02X->%02X" % (a + i, A[a + i], d[off + i]))
    if n:
        rows.append((a, n, sample))

print("  %-18s %-10s %s" % ("地址(256B块)", "差异数", "差异示例"))
for a, n, s in rows:
    print("      0x%04X        %3d/256   %s" % (a, n, " ".join(s)))

print()
print("=" * 84)
print("★ 连续差异段归并（只看最显著的）")
print("=" * 84)
alle = []
for a, n, s in rows:
    for i in range(256):
        if d[a - BASE + i] != A[a + i]:
            alle.append((a + i, A[a + i], d[a - BASE + i]))
alle.sort()
if alle:
    runs = []
    st = alle[0][0]; pv = alle[0][0]; items = [alle[0]]
    for x in alle[1:]:
        if x[0] == pv + 1:
            pv = x[0]; items.append(x)
        else:
            runs.append((st, pv, items)); st = x[0]; pv = x[0]; items = [x]
    runs.append((st, pv, items))
    for s, e, it in sorted(runs, key=lambda r: -(r[1] - r[0]))[:15]:
        print("  0x%04X-0x%04X (%3d B)  %s"
              % (s, e, e - s + 1,
                 " ".join("%02X->%02X" % (v, w) for _, v, w in it[:6])))
    print()
    print("  连续段总数 %d ；差异字节总数 %d" % (len(runs), len(alle)))
else:
    print("  无差异")

print()
print("=" * 84)
print("★ 压力帧族 0x5F00 专项（v2，已脱离读失败）")
print("=" * 84)
for a in range(0x5F00, 0x5F40, 16):
    va = " ".join("%02X" % A[a + i] for i in range(16))
    vd = d[a - BASE:a - BASE + 16].hex(' ').upper()
    print("  0x%04X  正常: %s" % (a, va))
    print("            退化: %s   %s" % (vd, "★差异" if va != vd else ""))
