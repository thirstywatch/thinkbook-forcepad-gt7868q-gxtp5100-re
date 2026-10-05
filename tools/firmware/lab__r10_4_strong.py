# -*- coding: utf-8 -*-
"""R10-4 ★★★ 强判据：在 5 个真实 Berlin/9916 cfg 里找「5 块面板长宽比一致」的相邻 u16 对
   真 (X,Y) 分辨率对 的特征：① 5 份该位置的值都不同（面板不同）② 5 个比值彼此一致（长宽比同）
   同时对本机 GT7868Q 的 cfg 做同样检验（本机 vs capA 两块板）"""
import os, json, base64

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "_r10")
NAMES = ['ihex-m16-TM', 'ihex-m16-GVO', 'lfs-moto-cybert', 'lfs-moto-dubai-csot', 'lfs-xiaomi-manet']
TEXT = {'ihex-m16-TM', 'ihex-m16-GVO'}


def ihex_decode(txt):
    mem, hi = {}, 0
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith(':'):
            continue
        try:
            b = bytes.fromhex(line[1:])
        except ValueError:
            continue
        if len(b) < 5:
            continue
        ln, addr, typ = b[0], (b[1] << 8) | b[2], b[3]
        if typ == 0x00:
            for i in range(ln):
                mem[hi + addr + i] = b[4 + i]
        elif typ == 0x02:
            hi = ((b[4] << 8) | b[5]) << 4
        elif typ == 0x04:
            hi = ((b[4] << 8) | b[5]) << 16
        elif typ == 0x01:
            break
    if not mem:
        return b''
    lo, h = min(mem), max(mem)
    return bytes(mem.get(i, 0) for i in range(lo, h + 1))


def u16(b, o): return b[o] | (b[o+1] << 8)
def u32(b, o): return int.from_bytes(b[o:o+4], 'little')

CF = {}
for nm in NAMES:
    p = os.path.join(TMP, nm + ".dat")
    if not os.path.exists(p):
        continue
    d = open(p, 'rb').read()
    if nm in TEXT:
        j = json.loads(d.decode('utf-8', 'replace'))
        d = ihex_decode(base64.b64decode(j["content"]).decode('utf-8', 'replace'))
    o = u16(d, 16); pl = u32(d, o)
    CF[nm] = d[o + 121:o + pl]
keys = list(CF)
n = min(len(CF[k]) for k in keys)
print(f"5 份 Berlin/9916 cfg，共同长度 {n} B\n")

print("=" * 100)
print("### ★★★ 判据：相邻 (u16, u16) 对，5 份比值彼此一致（±1%）且 5 份值都不同")
print("=" * 100)
for en in ('big', 'little'):
    hits = []
    for p in range(0, n - 4):
        vals = [int.from_bytes(CF[k][p:p+2], en) for k in keys]
        vals2 = [int.from_bytes(CF[k][p+2:p+4], en) for k in keys]
        if min(vals + vals2) < 300 or max(vals + vals2) > 40000:
            continue
        if len(set(vals)) < 4 or len(set(vals2)) < 4:
            continue
        rs = [a / b for a, b in zip(vals, vals2) if b]
        if min(rs) < 1.2:
            continue
        if (max(rs) - min(rs)) / min(rs) > 0.01:      # 5 个比值一致到 1% 内
            continue
        hits.append((p, vals, vals2, sum(rs)/len(rs)))
    print(f"\n  --- {en}-endian：命中 {len(hits)} 处 ---")
    for p, v1, v2, r in hits[:12]:
        print(f"    +0x{p:04x}  X={v1}  Y={v2}   比值 {r:.4f}")

print("\n" + "=" * 100)
print("### 对照：本机 GT7868Q 的 cfg（本机 vs capA 两块板）跑同一判据")
print("=" * 100)
O = open(os.path.join(HERE, 'orig_TB14P.bin'), 'rb').read()
ours = O[0x4C:0x4C + 1024]
capA = open(os.path.join(HERE, 'cap22001E0D.Cap'), 'rb').read()
best = (0, -1.0)
for off in range(len(capA[:0x4F0]) - 1024):
    m = sum(1 for i in range(1024) if capA[off+i] == ours[i]) / 1024
    if m > best[1]:
        best = (off, m)
offA = best[0]
capAcfg = capA[offA:offA + 1024]
print(f"  capA cfg @0x{offA:x}  与本机相同率 {100*best[1]:.1f}%")
# 只有两块板，无法做"5 份比值一致"，改做：找比值与两块板各自的物理长宽比都吻合的对
# 本机物理 135x80 -> 1.6875 ; capA 未知 => 只报"两块板都给出 >1.2 且比值接近"的对
for en in ('big', 'little'):
    hits = []
    for p in range(0, 1022):
        vo1 = int.from_bytes(ours[p:p+2], en); vo2 = int.from_bytes(ours[p+2:p+4], en)
        va1 = int.from_bytes(capAcfg[p:p+2], en); va2 = int.from_bytes(capAcfg[p+2:p+4], en)
        if min(vo1, vo2, va1, va2) < 300 or max(vo1, vo2, va1, va2) > 40000:
            continue
        if vo1 == va1 and vo2 == va2:
            continue
        r1 = vo1 / vo2 if vo2 else 0
        r2 = va1 / va2 if va2 else 0
        if r1 < 1.2 or r2 < 1.2:
            continue
        if abs(r1 - r2) / max(r1, r2) > 0.06:      # 两板比值接近（6% 内）
            continue
        hits.append((p, vo1, vo2, r1, va1, va2, r2))
    print(f"\n  --- 本机 cfg {en}-endian：命中 {len(hits)} 处 ---")
    for p, vo1, vo2, r1, va1, va2, r2 in hits[:12]:
        star = '  ★★★ 已知的 X/Y 点数位置' if p == 0x10F else ''
        print(f"    +0x{p:03x}  本机 {vo1}/{vo2}={r1:.3f}   capA {va1}/{va2}={r2:.3f}{star}")
