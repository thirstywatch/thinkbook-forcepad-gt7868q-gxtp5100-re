#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_upstream.py -- 跨全部 ACPI 表搜索"振动 IC 上游"相关线索。
只读。输出每个命中的 文件 + 偏移 + 上下文 ASCII。
"""
import os, sys, glob, json

D = sys.argv[1] if len(sys.argv) > 1 else 'acpi_all'
PATTERNS = [
    # 总线 / 控制器
    'I2C0','I2C1','I2C2','I2C3','I2C4','I2C5','I2C6','I2C7',
    'SMB0','SMB1','SMB2','SMBU','SBUS','SMBU','SBUS',
    # EC
    'PNP0C09','LPCB','EC0_','EC__','H_EC','ECDT',
    # 触控板
    'TPAD','GXTP5100','GXTP','GT7868',
    # 我们怀疑的触觉/上游名字
    'MLR1','MLR2','MOFD','MMCM','MBGS','MPL1','MPL2','PL1V','PL2V',
    'WMI5','DSIF','LPWR','LSCN','OVTP','SDRF',
    # 触觉关键词
    'LRA','HAPTIC','Haptic','haptic','VIBR','Vibr','MOTOR','Motor','TRIG','Trig',
    'AW869','AW86','CA4F','Awinic','AWINIC',
    # 其他可能的执行器
    'FF00','WMI','_WDG','_DSM',
]

def strings(buf, minlen=4):
    out, cur, st = [], [], 0
    for i, c in enumerate(buf):
        if 32 <= c < 127:
            if not cur: st = i
            cur.append(chr(c))
        else:
            if len(cur) >= minlen: out.append((st, ''.join(cur)))
            cur = []
    if len(cur) >= minlen: out.append((st, ''.join(cur)))
    return out

files = sorted(glob.glob(os.path.join(D, '*.bin')))
report = {}
allstr = {}
for fp in files:
    b = open(fp, 'rb').read()
    name = os.path.basename(fp)
    allstr[name] = strings(b, 4)
    for p in PATTERNS:
        nb = p.encode()
        offs = []
        i = b.find(nb)
        while i >= 0 and len(offs) < 40:
            offs.append(i); i = b.find(nb, i + 1)
        if offs:
            report.setdefault(p, {})[name] = offs

print("=" * 90)
print("命中矩阵（模式 -> 文件:命中数）")
print("=" * 90)
for p in PATTERNS:
    if p in report:
        tot = sum(len(v) for v in report[p].values())
        detail = ', '.join('%s:%d' % (f, len(o)) for f, o in sorted(report[p].items()))
        print("  %-10s total=%-4d  %s" % (p, tot, detail))
    else:
        print("  %-10s ---" % p)

json.dump(report, open(os.path.join(D, '_scan_upstream.json'), 'w'),
          ensure_ascii=False, indent=2)

# 重点：把含 LRA/haptic/TRIG/AW 的表全文串出来
print()
print("=" * 90)
print("含触觉相关关键词的表 -> 全部可读串")
print("=" * 90)
KEY = ('LRA','HAPT','hapt','VIBR','Vibr','MOTOR','Motor','TRIG','Trig','AW86','CA4F','Awinic')
for name, ss in allstr.items():
    hk = [(o, s) for (o, s) in ss if any(k in s for k in KEY)]
    if hk:
        print("--- %s ---" % name)
        for o, s in hk[:60]:
            print("   0x%06X: %s" % (o, s))
