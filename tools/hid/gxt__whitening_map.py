# -*- coding: utf-8 -*-
"""
用已验证的判据（|rel|<=8 占比）扫整个固件，找出所有"非白化"区域。
标尺：随机/白化 0.072 | 0x19000 0.229 | 0x1E000 0.328 | 真代码 0.543
"""
import os, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "whitening_map.txt")
data = open(FW, "rb").read()
L = len(data)
lines = []
def w(s=""):
    lines.append(s); print(s)

RELOPS = set((0x80,0x70,0x60,0x50,0x40,0x30,0x20,0x10,
              0x01,0x21,0x41,0x61,0x81,0xa1,0xc1,0xe1,
              0x11,0x31,0x51,0x71,0x91,0xb1,0xd1,0xf1))

def relscore(b):
    n = 0; ok = 0
    for i in range(len(b)-1):
        if b[i] in RELOPS:
            rel = b[i+1] - 256 if b[i+1] >= 128 else b[i+1]
            n += 1
            if abs(rel) <= 8: ok += 1
    return (ok/n if n >= 6 else None), n

def H(b):
    import math
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())

w("=" * 84)
w("全固件白化地图（判据 |rel|<=8 占比 · 窗口 512 B · 步长 512 B）")
w("=" * 84)
w()
w("  标尺: 随机/白化 0.072 | 0x19000 0.229 | 0x1E000 0.328 | 真代码 0x00000 0.543")
w()
w("  偏移       rel    熵     零%   判定")
map_rows = []
for o in range(0, L - 512 + 1, 512):
    win = data[o:o+512]
    sc, n = relscore(win)
    if sc is None:
        continue
    map_rows.append((o, sc))
    if sc >= 0.35:   v = "★★ 强代码"
    elif sc >= 0.20: v = "★  弱/混合"
    else:            v = "·  白化"
    if sc >= 0.14:   # 只打印非白化的，避免刷屏
        w("  0x%05X  %.3f  %.3f  %4.1f  %s"
          % (o, sc, H(win), win.count(0)/512*100, v))
w()

w("【非白化窗口汇总（rel >= 0.20）】")
nonwh = [(o, s) for o, s in map_rows if s >= 0.20]
w("  共 %d 个窗口（每窗口 512 B，占全文件 %.1f%%）"
  % (len(nonwh), 100*len(nonwh)*512/L))
# 聚类成区间
groups = []
if nonwh:
    cur = [nonwh[0]]
    for o, s in nonwh[1:]:
        if o - cur[-1][0] <= 1024:
            cur.append((o, s))
        else:
            groups.append(cur); cur = [(o, s)]
    groups.append(cur)
w("  聚成 %d 个连续区间:" % len(groups))
for g in groups:
    a = g[0][0]; b = g[-1][0] + 512
    mx = max(s for _, s in g)
    w("    0x%05X – 0x%05X  (%6d B)  峰值 rel %.3f" % (a, b, b-a, mx))
w()

w("【与官方分区的交叉】")
PARTS = [(0x16000,0x2000,0x03),(0x06000,0x2000,0x03),(0x08000,0x2000,0x03),
         (0x0A000,0x2000,0x03),(0x0C000,0x2000,0x03),(0x1E000,0x2000,0x03),
         (0x10000,0x2000,0x03),(0x01000,0x3000,0x02),(0x00000,0x1000,0x02),
         (0x04000,0x2000,0x03),(0x13000,0x3000,0x02),(0x12000,0x1000,0x02)]
w("  分区         type  熵      rel    包含的非白化窗口")
for addr, size, typ in sorted(PARTS):
    seg = data[addr:addr+size]
    sc, n = relscore(seg)
    cnt = sum(1 for o, s in nonwh if addr <= o < addr+size)
    w("  0x%05X(%5d)  0x%02X  %.3f   %s   %d"
      % (addr, size, typ, H(seg), ("%.3f" % sc) if sc else " --  ", cnt))
w()

w("【未分配区（缺口）也查一遍】")
GAPS = [(0x0E000, 0x2000), (0x14000, 0x2000)]
for addr, size in GAPS:
    seg = data[addr:addr+size]
    sc, n = relscore(seg)
    w("  0x%05X (%d B) 熵 %.3f  rel %s  零%% %.1f"
      % (addr, size, H(seg), ("%.3f" % sc) if sc else "--", seg.count(0)/size*100))
w()

w("【尾部 30,556 B（容器尾）】")
tail = data[0x20000:]
sc, n = relscore(tail)
w("  0x20000–0x%X  熵 %.3f  rel %s  零%% %.1f"
  % (L, H(tail), ("%.3f" % sc) if sc else "--", tail.count(0)/len(tail)*100))
# 尾部是否有明文头
w("  尾部前 64 B: %s" % tail[:64].hex(" "))
# 找 ASCII
runs = []; cur = b""
for b_ in tail:
    if 0x20 <= b_ < 0x7f: cur += bytes([b_])
    else:
        if len(cur) >= 5: runs.append(cur)
        cur = b""
if len(cur) >= 5: runs.append(cur)
w("  ASCII 串(>=5): %s" % runs[:20])
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
