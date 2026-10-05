# -*- coding: utf-8 -*-
"""R4-9（权威版，替代 s7 的错误偏移）：
   三份 GT7868Q 逐块相似度 + 版本轴孤立单字节差异 = 字段边界定位"""
import numpy as np, collections

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0), 'capB': ('cap26002816.Cap', 0x4F0)}
INFO = {'本机': 'CID=1C VID=2.3.5', 'capA': 'CID=0C VID=2.0.30', 'capB': 'CID=0C VID=2.0.40'}

def load(p, base):
    d = open(p, 'rb').read(); n = d[base+27]; q = base+32; rows = []
    for _ in range(n):
        rows.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                     ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
    tot = sum(r[1] for r in rows)
    raw = np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)
    return rows, raw

R, RAW = {}, {}
for k, (p, b) in S.items():
    R[k], RAW[k] = load(p, b)
ROWS = R['本机']
OFF = np.cumsum([0] + [r[1] for r in ROWS])       # ★ 子固件在"数据区"内的偏移（从 0 起）
print("表三份一致:", R['本机'] == R['capA'] == R['capB'])
print("偏移表:", [(hex(r[2]), r[1]) for r in ROWS][:4], "...")

def seg(x, y, o, l):
    d = np.nonzero(x[o:o+l] != y[o:o+l])[0]
    if len(d) == 0: return d, []
    out = []; s = d[0]; p = d[0]
    for v in d[1:]:
        if v == p+1: p = v
        else: out.append((s, p)); s = v; p = v
    out.append((s, p)); return d, out

print("\n" + "=" * 104)
print("### 1（权威）逐块相似度：版本轴 = capA(2.0.30)→capB(2.0.40) 同 CID；机型轴 = 本机(CID 1C) vs capA(CID 0C)")
print("=" * 104)
print(f"  {'idx':>3} {'type':>5} {'flash':>9} {'size':>6} | {'版本轴相同%':>11} {'机型轴相同%':>11} | {'版本差异字节':>12} {'最长段':>7} {'段数':>6}  判读")
TAB = []
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    dv, rv = seg(RAW['capA'], RAW['capB'], o, ln)
    dm, rm = seg(RAW['本机'], RAW['capA'], o, ln)
    sv = 100*(ln-len(dv))/ln; sm = 100*(ln-len(dm))/ln
    lmax = max((e-s+1 for s, e in rv), default=0)
    kind = ("★芯片级常量" if sv == 100 else
            ("★版本常量/字段极少" if len(rv) and lmax <= 4 and len(dv) < ln*0.06 else
             ("机型主变" if sm < sv-20 else "混合")))
    TAB.append((i, t, ad, ln, sv, sm, len(dv), lmax, len(rv)))
    print(f"  {i:>3} {t:#05x} {ad:#09x} {ln:>6} | {sv:>11.2f} {sm:>11.2f} | {len(dv):>12} {lmax:>7} {len(rv):>6}  {kind}")

print("\n" + "=" * 104)
print("### 2 ★ 版本轴孤立单字节差异 —— 字段边界定位")
print("=" * 104)
for i, t, ad, ln, sv, sm, nd, lmax, nr in TAB:
    if not nd or lmax > 4: continue
    o = OFF[i]
    d = np.nonzero(RAW['capA'][o:o+ln] != RAW['capB'][o:o+ln])[0]
    print(f"\n  --- idx{i} flash {ad:#07x}  {len(d)} 处孤立差异 ---")
    print(f"      偏移 mod4 : {dict(sorted(collections.Counter((d%4).tolist()).items()))}")
    print(f"      偏移 mod8 : {dict(sorted(collections.Counter((d%8).tolist()).items()))}")
    print(f"      偏移 mod16: {dict(sorted(collections.Counter((d%16).tolist()).items()))}")
    print(f"      偏移区间  : min=+0x{d.min():x} max=+0x{d.max():x}  （块长 0x{ln:x}）")
    print(f"      前 24 处（偏移: capA→capB, 差值）:")
    for v in d[:24]:
        a, b = int(RAW['capA'][o+v]), int(RAW['capB'][o+v])
        print(f"        +0x{v:04x} (mod16={v%16:>2})  {a:02x} -> {b:02x}   Δ={b-a:+4d}   "
              f"{'零→非零' if a==0 and b else ('非零→零' if a and b==0 else '值变')}")
    nz = sum(1 for v in d if RAW['capA'][o+v] == 0 or RAW['capB'][o+v] == 0)
    print(f"      与 0 相关的差异 = {nz}/{len(d)}")

print("\n" + "=" * 104)
print("### 3 ★ 机型轴差异的'区域'结构：是否成片（vs 版本轴的散点）")
print("=" * 104)
for i, t, ad, ln, sv, sm, nd, lmax, nr in TAB:
    o = OFF[i]
    dm, rm = seg(RAW['本机'], RAW['capA'], o, ln)
    if not len(dm): continue
    blk = np.zeros(ln, dtype=int)
    for s, e in rm: blk[s:e+1] = 1
    prof = blk.reshape(16, -1).mean(axis=1)
    print(f"  idx{i:>2} {ad:#07x} 段数={len(rm):>4} 最长={max(e-s+1 for s,e in rm):>4} "
          f"差异密度16等分: " + " ".join(f"{100*v:3.0f}" for v in prof) + "%")

print("\n" + "=" * 104)
print("### 4 ★ 跨块一致性：版本轴差异'位置'能否跨块对齐（同一记录布局？）")
print("=" * 104)
sets = {}
for i, t, ad, ln, sv, sm, nd, lmax, nr in TAB:
    if lmax <= 4 and nd:
        o = OFF[i]
        sets[i] = set(np.nonzero(RAW['capA'][o:o+ln] != RAW['capB'][o:o+ln])[0].tolist())
print("  参与比较的块:", {k: len(v) for k, v in sets.items()})
ks = list(sets)
for a in range(len(ks)):
    for b in range(a+1, len(ks)):
        ia, ib = ks[a], ks[b]
        # 比较 mod 16 位置直方
        ha = collections.Counter((np.array(sorted(sets[ia])) % 16).tolist())
        hb = collections.Counter((np.array(sorted(sets[ib])) % 16).tolist())
        print(f"  idx{ia} vs idx{ib}: mod16 直方 {[ha.get(j,0) for j in range(16)]} / "
              f"{[hb.get(j,0) for j in range(16)]}")
