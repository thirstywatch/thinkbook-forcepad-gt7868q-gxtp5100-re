# -*- coding: utf-8 -*-
"""加密结构审计 第二轮 —— 判定「到底是什么加密」，以及跨镜像共用密钥的范围。
只读本机文件，不碰任何设备。"""

import io, os, collections

BIN = r'C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN'
HDR = bytes.fromhex('000188FA') + b'\x5f\x37' + b'YELSTO' + bytes.fromhex('000006') + b'7868Q'
PL = 100608

out = []
def P(s=''):
    print(s); out.append(str(s))

d = open(BIN, 'rb').read()
i = d.find(HDR)
ct = d[i + 24: i + PL]
P("密文 %d 字节；载荷A 在容器 0x%X" % (len(ct), i))
P()

P("=" * 76)
P("① 自相关：ct[k] vs ct[k+lag] 的字节匹配率（随机期望 0.39%）")
P("=" * 76)
for lag in (8, 16, 32, 64, 128, 256, 512, 1024, 1084, 2048, 2168, 4096, 8192, 16384, 32768):
    if lag >= len(ct):
        continue
    n = len(ct) - lag
    idxs = range(0, n, 7)
    tot = 0; m = 0
    for k in idxs:
        tot += 1
        if ct[k] == ct[k + lag]:
            m += 1
    P("   lag %6d : %5.2f%%   (采样 %d)" % (lag, 100.0 * m / tot, tot))
P()

P("=" * 76)
P("② 重复块率 vs 块大小（都取最佳相位；随机期望≈0）")
P("=" * 76)
for n in (4, 8, 16, 32, 64):
    best = (0, 0, 0)
    for ph in range(n):
        bs = [ct[ph + k * n: ph + (k + 1) * n] for k in range((len(ct) - ph) // n)]
        c = collections.Counter(bs)
        dup = sum(v - 1 for v in c.values() if v > 1)
        if dup > best[1]:
            best = (ph, dup, len(bs))
    ph, dup, tot = best
    P("   %2d 字节块 : 最佳相位 %2d  重复 %5d / %5d  = %5.2f%%" % (n, ph, dup, tot, 100.0 * dup / tot))
P()

P("=" * 76)
P("③ 最长重复内容（64 字节窗口索引，取出现次数最多的 8 组）")
P("=" * 76)
W = 64
idx = collections.defaultdict(list)
for k in range(0, len(ct) - W + 1):
    idx[ct[k:k + W]].append(k)
top = sorted(((len(v), v) for v in idx.values() if len(v) >= 2), key=lambda x: -x[0])[:8]
for cnt, offs in top:
    o0 = offs[0]
    L = W
    while o0 + L < len(ct) and all(ct[o + L] == ct[o0 + L] for o in offs):
        L += 1
    gaps = [offs[k + 1] - offs[k] for k in range(len(offs) - 1)]
    gc = collections.Counter(gaps)
    P("   出现 %-3d 次  可扩展至 %-5d 字节" % (cnt, L))
    P("       前几个偏移 %s" % [hex(o) for o in offs[:8]])
    P("       间距直方图 %s" % gc.most_common(6))
P()

P("=" * 76)
P("④ 跨镜像：共用密文块的比例（抽样，块长 16）")
P("=" * 76)
caps = [
    ("Cap 22001E0D（2021 代）",
     r'<WORKSPACE>'),
    ("Cap 26002816（2020 代）",
     r'<WORKSPACE>'),
]
C = {}
for nm, cp in caps:
    if os.path.exists(cp):
        C[nm] = open(cp, 'rb').read()
    else:
        P("   [缺失] %s" % nm)
tot = 0; hit = dict((k, 0) for k in C)
step = 16 * 53
for k in range(0, len(ct) - 16, step):
    blk = ct[k:k + 16]
    tot += 1
    for nm, o in C.items():
        if o.find(blk) >= 0:
            hit[nm] += 1
for nm in C:
    P("   %-24s 抽样 %4d 块  命中 %4d  = %5.1f%%" % (nm, tot, hit[nm], 100.0 * hit[nm] / tot))

full = [ct[k:k + 16] for k in range(0, len(ct) - 16, 16)]
if len(C) >= 2:
    ks = list(C)
    hits = 0; tot2 = 0
    for k in range(0, len(C[ks[0]]) - 16, 16 * 61):
        blk = C[ks[0]][k:k + 16]
        tot2 += 1
        if C[ks[1]].find(blk) >= 0:
            hits += 1
    P("   两个老 Cap 互相之间：抽样 %d 块，命中 %d = %.1f%%" % (tot2, hits, 100.0 * hits / tot2 if tot2 else 0))
P()

P("=" * 76)
P("⑤ 重复块的真实偏移取同余类（phase 4，真实偏移 = 4 + 16k）")
P("=" * 76)
n = 16; ph = 4
bs = [ct[ph + k * n: ph + (k + 1) * n] for k in range((len(ct) - ph) // n)]
c = collections.Counter(bs)
rep = [(b, v) for b, v in c.items() if v >= 3]
alloff = []
for b, v in rep:
    offs = [ph + k * n for k, x in enumerate(bs) if x == b]
    alloff += offs
if alloff:
    for mod in (256, 512, 1024, 2048, 4096):
        cnt = collections.Counter(o % mod for o in alloff)
        P("   mod %5d : 最集中的余数 %s" % (mod, cnt.most_common(3)))
    P("   参与统计的重复块偏移数 %d（来自 %d 个块）" % (len(alloff), len(rep)))
P()

o = r'<LAB>\touchpad-lab\re\aes_payload_audit2_out.txt'
io.open(o, 'w', encoding='utf-8').write('\n'.join(out))
print("[已写] " + o)
