# -*- coding: utf-8 -*-
"""R7-3: 本机 cfg body 的 TLV 解剖 + 机型轴标注 = 字段图
⚠️ 撤回说明：R7-2 §3 的"u16 对/长宽比"筛法【没有分辨力】——511x511/2≈13 万对候选里，
   任何比值窗口都会命中成百上千对，排序只会把最接近的抬出来。该节作废，不作为证据。
   本脚本改用与项目 §5.2 同一套纪律：① 覆盖率  ② TAG 单调性  ③ 与"声明条目数"一致性。"""
import numpy as np, collections

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
model_spec = (a == b) & (a != o)
ver_spec = (a != b)

print("=" * 100)
print("### 1 帧序判定（自 ~0x100 起），两种走法头对头对比")
print("=" * 100)


def parse(cfg, start, order):
    i, fr = start, []
    while i < 1024 - 1:
        x, y = cfg[i], cfg[i + 1]
        ln, tg = (x, y) if order == 'LEN_TAG' else (y, x)
        if ln >= 2 and i + ln <= 1024:
            fr.append((i, tg, ln, cfg[i + 2:i + ln])); i += ln
        else:
            i += 1
    return fr


for order in ('LEN_TAG', 'TAG_LEN'):
    best = None
    for st in range(0x60, 0x140):
        fr = parse(ours, st, order)
        cov = sum(f[2] for f in fr)
        inc = sum(1 for k in range(1, len(fr)) if fr[k][1] > fr[k - 1][1])
        sc = (cov, inc)
        if best is None or sc > best[0]: best = (sc, st, fr)
    (cov, inc), st, fr = best
    print(f"  {order:<9} 最优起点 +0x{st:03x}  帧 {len(fr):>3}  覆盖 {cov}/1024 = {100*cov/1024:5.1f}%  "
          f"TAG 递增 {inc}/{max(1,len(fr)-1)}  首 8 个 TAG {[hex(f[1]) for f in fr[:8]]}")

print("\n" + "=" * 100)
print("### 2 ★★★ 采用帧序解析 → TLV 全表（含机型轴标注）")
print("=" * 100)
ORDER = 'TAG_LEN'
# 起点选覆盖最好的那个
best = None
for st in range(0x60, 0x140):
    fr = parse(ours, st, ORDER)
    cov = sum(f[2] for f in fr)
    inc = sum(1 for k in range(1, len(fr)) if fr[k][1] > fr[k - 1][1])
    if best is None or (cov, inc) > best[0]: best = ((cov, inc), st, fr)
(cov, inc), st, fr = best
print(f"  起点 +0x{st:03x}  覆盖 {100*cov/1024:.1f}%  TAG 递增 {inc}/{len(fr)-1}")
print(f"  {'偏移':>7} {'TAG':>5} {'LEN':>4}  机型轴  版本轴  载荷（前 20 B）")
for off, tg, ln, pl in fr:
    ms = int(model_spec[off:off+ln].sum()); vs = int(ver_spec[off:off+ln].sum())
    tag = ('★机型' if ms > ln*0.4 else ('机型少' if ms else '同'))
    vtag = ('版本变' if vs > ln*0.4 else '')
    print(f"  +0x{off:03x} 0x{tg:02x} {ln:>4}  {tag:<6} {vtag:<6} {pl[:20].hex(' ')}")

print("\n" + "=" * 100)
print("### 3 ★★★ 关键候选值的定位（u16BE，因为本表按 BE 读得通）")
print("=" * 100)
# 把 TLV 区内所有 u16BE 列出来，与"机型相关"一起看
print(f"  {'绝对偏移':>9} {'u16BE':>7} {'u16LE':>7}  机型相关?  所属 TAG")
owner = {}
for off, tg, ln, pl in fr:
    for p in range(off, off+ln):
        owner[p] = tg
for p in range(0x100, 0x400 - 1, 1):
    be = (int(ours[p]) << 8) | int(ours[p+1])
    le = int(ours[p]) | (int(ours[p+1]) << 8)
    if be in (2000, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 150, 120, 100, 90, 80, 75, 70, 64, 60, 50, 48, 40, 32, 25, 24, 20, 16, 14, 12, 10) \
       or le in (2000, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 150, 120, 100, 90, 80, 75, 70, 64, 60, 50, 48, 40, 32, 25, 24, 20, 16, 14, 12, 10) \
       or be in (0x1036, 0x0864) or le in (0x1036, 0x0864):
        ms = bool(model_spec[p] or model_spec[p+1])
        print(f"  +0x{p:03x}   {be:>7} {le:>7}   {'★机型相关' if ms else '      '}   TAG 0x{owner.get(p,-1)&0xff:02x}")

print("\n" + "=" * 100)
print("### 4 本机 / capA 在 +0x100..+0x120 与 +0x330..+0x3A0 两段的并排")
print("=" * 100)
for lo, hi in ((0x100, 0x120), (0x330, 0x3A0)):
    print(f"  --- +0x{lo:03x}..+0x{hi:03x} ---")
    for p in range(lo, hi, 16):
        print(f"    本机  +0x{p:03x}  " + " ".join(f"{c:02x}" for c in ours[p:p+16]))
        print(f"    capA  +0x{p:03x}  " + " ".join(f"{c:02x}" for c in BODY['capA'][0xa4+p-0x0:0xa4+p-0x0+16])
              if False else f"    capA  +0x{p:03x}  " + " ".join(f"{c:02x}" for c in CFG['capA'][p:p+16]))
