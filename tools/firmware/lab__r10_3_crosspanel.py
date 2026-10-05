# -*- coding: utf-8 -*-
"""R10-3: 用 5 个真实 Berlin/9916 cfg 做跨面板对照 —— 验证「分辨率类字段占 cfg 内固定偏移」这个结构假设
   5 份来自同一芯片(9916)不同面板(TM/GVO/csot-tianma/manet)"""
import os, json, base64, collections

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "_r10")
NAMES = ['ihex-m16-TM', 'ihex-m16-GVO', 'lfs-moto-cybert', 'lfs-moto-dubai-csot', 'lfs-xiaomi-manet']
LBL = {'ihex-m16-TM': '9916 TM', 'ihex-m16-GVO': '9916 GVO', 'lfs-moto-cybert': '9916K cybert',
       'lfs-moto-dubai-csot': '9916 csot', 'lfs-xiaomi-manet': '9916R manet'}
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


def u16(b, o): return b[o] | (b[o + 1] << 8)
def u32(b, o): return int.from_bytes(b[o:o + 4], 'little')

CFGS = {}
for nm in NAMES:
    p = os.path.join(TMP, nm + ".dat")
    if not os.path.exists(p):
        print(f"[缺] {nm}"); continue
    d = open(p, 'rb').read()
    if nm in TEXT:
        j = json.loads(d.decode('utf-8', 'replace'))
        d = ihex_decode(base64.b64decode(j["content"]).decode('utf-8', 'replace'))
    size = u32(d, 0)
    pn = d[9]
    ov = [u16(d, 16 + 2 * i) for i in range(pn)]
    o = ov[0]
    pkg_len = u32(d, o)
    cfg = d[o + 121:o + pkg_len]
    CFGS[nm] = cfg
    print(f"  {LBL[nm]:<12} 文件 {len(d):>5} B  pkg_len {pkg_len:>5}  cfg 数据 {len(cfg):>5} B  "
          f"ic_type={d[o+4:o+19].split(bytes(1))[0].decode('latin-1')!r}")

print("\n" + "=" * 100)
print("### 1 跨面板逐字节差异剖面（5 份 cfg 数据，同相对偏移）")
print("=" * 100)
keys = list(CFGS)
n = min(len(CFGS[k]) for k in keys)
print(f"  共同长度 {n} B（取最短）")
stat = []
for p in range(n):
    vals = [CFGS[k][p] for k in keys]
    differ = len(set(vals))
    stat.append(differ)
same = sum(1 for v in stat if v == 1)
print(f"  5 份全同的字节 {same}/{n} ({100*same/n:.1f}%)")
print("  逐 64 B 的'5 份全同'比例：")
for a in range(0, n, 64):
    seg = stat[a:a+64]
    print(f"    +0x{a:04x}: {100*sum(1 for v in seg if v==1)/len(seg):5.1f}%", end="")
    if (a//64 + 1) % 4 == 0:
        print()

print("\n" + "=" * 100)
print("### 2 ★★★ 找「跨面板必变、且像分辨率」的 u16 位置（LE 与 BE 都试）")
print("=" * 100)
for en in ('little', 'big'):
    cands = []
    for p in range(0, n - 2):
        vals = [int.from_bytes(CFGS[k][p:p+2], en) for k in keys]
        if len(set(vals)) < 3:
            continue
        if not all(400 <= v <= 40000 for v in vals):
            continue
        mx, mn = max(vals), min(vals)
        if mn and 1.05 < mx / mn < 3.2:
            cands.append((p, vals))
    print(f"\n  --- {en}-endian：候选 {len(cands)} 处（跨面板变化 ≥3 种、值域 400..40000、最大/最小 1.05-3.2）---")
    for p, vals in cands[:20]:
        print(f"    +0x{p:04x}  {vals}   比值 {max(vals)/min(vals):.3f}")

print("\n" + "=" * 100)
print("### 3 对照：本机 GT7868Q 的 cfg（1024 B）在同样口径下的'机型轴变化位置'")
print("=" * 100)
D = HERE
O = open(os.path.join(D, 'orig_TB14P.bin'), 'rb').read()
ours = O[0x4C:0x4C + 1024]
capA = open(os.path.join(D, 'cap22001E0D.Cap'), 'rb').read()
def find_body(w, ref):
    wa = w; best = (0, -1.0)
    for off in range(len(wa) - 1024):
        m = float(sum(1 for i in range(1024) if wa[off+i] == ref[i]) / 1024)
        if m > best[1]: best = (off, m)
    return best
offA, _ = find_body(capA[:0x4F0], ours)
capAcfg = capA[offA:offA + 1024]
print(f"  capA cfg @0x{offA:x}")
for en in ('little', 'big'):
    out = []
    for p in range(0, 1022):
        vo = int.from_bytes(ours[p:p+2], en); va = int.from_bytes(capAcfg[p:p+2], en)
        if vo == va: continue
        if not all(400 <= v <= 40000 for v in (vo, va)): continue
        mx, mn = max(vo, va), min(vo, va)
        if mn and 1.05 < mx/mn < 3.2:
            out.append((p, vo, va, mx/mn))
    print(f"\n  --- 本机 cfg {en}-endian 候选 {len(out)} 处 ---")
    for p, vo, va, r in out[:14]:
        star = '  ★★★ 就是这里（已知 X/Y 点数）' if p in (0x10F, 0x111) else ''
        print(f"    +0x{p:03x}  本机 {vo:<6} capA {va:<6}  比值 {r:.3f}{star}")
