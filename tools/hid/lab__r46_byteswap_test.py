#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lab__r46_byteswap_test.py — 检验 A/B 差异是否为【字节序/相位】伪影

思路：若 snapA 与退化态的差异主要来自"读取时的字节序/相位不同"，
      则对其中一方施加（4B 反转 / 2B 反转 / 整体反转 / 相位平移）后，
      差异应【大幅下降】。
若变换后差异不降 ⇒ 差异是【真实的内容差异】（版本不同）。
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
fail = set(json.load(open(os.path.join(LOGS, 'gxt__degraded_failmap.json')))['bad'])
BASE = 0x4000

# 选一批【干净】的地址：不在失败图、正常态静态、无 EE
addrs = []
for off in range(0, len(d) - 4, 4):
    a = BASE + off
    if a in fail or (a - a % 64) in fail:
        continue
    addrs.append(a)
print("用于检验的地址数: %d" % len(addrs))


def diff_count(transform, label):
    same = 0; tot = 0
    for a in addrs:
        va = A.get(a)
        if va is None:
            continue
        off = a - BASE
        if transform == 'raw':
            vd = d[off]
        elif transform == 'rev4':
            if off % 4 != 0:
                continue
            vd = d[off - off % 4 + (3 - off % 4)]
        elif transform == 'rev2':
            vd = d[off - off % 2 + (1 - off % 2)]
        elif transform == 'nibble':
            vd = ((d[off] & 0x0F) << 4) | ((d[off] & 0xF0) >> 4)
        else:
            vd = d[off]
        tot += 1
        if va == vd:
            same += 1
    print("  %-24s 相同 %6d / %6d = %5.2f%%   差异 %5.2f%%"
          % (label, same, tot, same / tot * 100, 100 - same / tot * 100))
    return same / tot


print()
print("=== 变换实验：谁能把差异降下来？ ===")
diff_count('raw', '原样比对')
diff_count('rev2', '2 字节反转')
diff_count('rev4', '4 字节反转')
diff_count('nibble', '高低半字节互换')

# 额外：在同一 4B 组内做 4 种旋转
print()
print("=== 4 字节组内旋转（相位）===")
for k in range(4):
    same = 0; tot = 0
    for a in addrs:
        va = A.get(a)
        if va is None or (a - BASE) % 4 != 0:
            continue
        off = a - BASE
        vd = d[off - off % 4 + (off + k) % 4]
        tot += 1
        if va == vd:
            same += 1
    print("  旋转 %d：相同 %.2f%%  差异 %.2f%%" % (k, same / tot * 100, 100 - same / tot * 100))

# 对照：把"退化态自己"与"另一个快照"比（内部一致性上限）
print()
print("=== 对照：snapB（正常态另一种）vs snapA ===")
same = 0; tot = 0
for a in addrs:
    va = A.get(a); vb = B.get(a)
    if va is None or vb is None:
        continue
    tot += 1
    if va == vb:
        same += 1
print("  相同 %d/%d = %.2f%%" % (same, tot, same / tot * 100))
