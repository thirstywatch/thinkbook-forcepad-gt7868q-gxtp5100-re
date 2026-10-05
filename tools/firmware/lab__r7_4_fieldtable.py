# -*- coding: utf-8 -*-
"""R7-4: 本机 cfg 寄存器像的【字段表】—— 机型相关段逐段给出三份取值 + u16BE/u16LE 解读"""
import numpy as np

S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0),
     'capB': ('cap26002816.Cap', 0x4F0)}
BODY = {k: open(p, 'rb').read()[:img] for k, (p, img) in S.items()}
ours = BODY['本机'][0x4C:0x4C + 1024]


def find_body(w, ref):
    wa = np.frombuffer(w, np.uint8); ra = np.frombuffer(ref, np.uint8)
    best = (0, -1.0)
    for off in range(len(wa) - 1024):
        m = float((wa[off:off + 1024] == ra).mean())
        if m > best[1]: best = (off, m)
    return best


CFG = {'本机': ours}
for k in ('capA', 'capB'):
    off, _ = find_body(BODY[k], ours)
    CFG[k] = BODY[k][off:off + 1024]

o = np.frombuffer(CFG['本机'], np.uint8)
a = np.frombuffer(CFG['capA'], np.uint8)
b = np.frombuffer(CFG['capB'], np.uint8)
ms = (a == b) & (a != o)

print("=" * 104)
print("### 机型相关段（capA==capB 且 != 本机）—— 逐段三份取值 + 数值解读")
print("=" * 104)
runs, i = [], 0
while i < 1024:
    if ms[i]:
        j = i
        while j < 1024 and ms[j]: j += 1
        runs.append((i, j - 1)); i = j
    else: i += 1
big = [r for r in runs if r[1] - r[0] >= 3]
print(f"  机型相关 {int(ms.sum())}/1024；≥4 B 的段 {len(big)} 个\n")
for s, e in big:
    n = e - s + 1
    print(f"  +0x{s:03x}..+0x{e:03x}  ({n} B)")
    print(f"      本机  {' '.join(f'{v:02x}' for v in o[s:e+1])}")
    print(f"      capA  {' '.join(f'{v:02x}' for v in a[s:e+1])}")
    print(f"      capB  {' '.join(f'{v:02x}' for v in b[s:e+1])}")
    if n >= 4:
        bo = [int.from_bytes(bytes(p), 'big') for p in o[s:e+1][:n//2*2].reshape(-1, 2)]
        ba = [int.from_bytes(bytes(p), 'big') for p in a[s:e+1][:n//2*2].reshape(-1, 2)]
        lo = [int.from_bytes(bytes(p), 'little') for p in o[s:e+1][:n//2*2].reshape(-1, 2)]
        la = [int.from_bytes(bytes(p), 'little') for p in a[s:e+1][:n//2*2].reshape(-1, 2)]
        print(f"      u16BE  本机 {bo}    capA {ba}")
        print(f"      u16LE  本机 {lo}    capA {la}")
    print()

print("=" * 104)
print("### ★ 汇总：三份在'机型相关'位置上的 u16BE 取值（可直接抄进报告）")
print("=" * 104)
print(f"  {'偏移':>7} {'本机':>7} {'capA':>7} {'capB':>7}  {'本机/capA':>9}  备注")
for s, e in big:
    for p in range(s, e, 2):
        if p + 1 > e: break
        vo = int.from_bytes(bytes(o[p:p+2]), 'big')
        va = int.from_bytes(bytes(a[p:p+2]), 'big')
        vb = int.from_bytes(bytes(b[p:p+2]), 'big')
        if vo == va == vb: continue
        note = ''
        if va:
            r = vo / va
            if 1.2 < r < 2.2: note = f'比值 {r:.3f}'
        print(f"  +0x{p:03x}  {vo:>7} {va:>7} {vb:>7}  {vo/max(1,va):>9.3f}  {note}")
