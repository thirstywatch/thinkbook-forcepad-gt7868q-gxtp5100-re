# -*- coding: utf-8 -*-
"""
0x1E000 到底是什么：
 1. 定长记录 pitch 搜索（自相关，在字节级与 u16 级）
 2. 按 pitch 分组后，看每列是否"取值域窄"（= 表格特征）
 3. 与 0x19000 (官方 CFG_FLASH_ADDR) 对照
 4. 小端 u16 渲染，看是否是 (addr, value) 对
"""
import os, math, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "region_1E000.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

w("=" * 78)
w("0x1E000 定性")
w("=" * 78); w()

SEG = data[0x1E000:0x20000]
N = len(SEG)

def autocorr(b, lag):
    if lag <= 0 or lag >= len(b): return 0.0
    n = len(b) - lag
    return sum(1 for i in range(n) if b[i] == b[i+lag]) / n

w("【1】字节级自相关 · 找记录 pitch")
cands = []
for lag in range(2, 513):
    r = autocorr(SEG, lag)
    cands.append((r, lag))
cands.sort(reverse=True)
w("  基线 (随机期望) = 1/256 = 0.0039")
w("  Top-20 lag:")
for r, lag in cands[:20]:
    w("    lag %4d  →  相等率 %.4f  (×%.1f 基线)" % (lag, r, r/0.00390625))
w()

# 只看 2 的幂与小整数
w("  特定 lag 详细:")
for lag in (2,4,8,12,16,20,24,28,32,40,48,56,64,72,80,96,112,128,192,256,512):
    r = autocorr(SEG, lag)
    w("    lag %4d  →  %.4f  (×%.1f)" % (lag, r, r/0.00390625))
w()

w("【2】u16 级自相关")
u16 = [int.from_bytes(SEG[i:i+2], "little") for i in range(0, N-1, 2)]
def ac16(lag):
    n = len(u16) - lag
    if n <= 0: return 0.0
    return sum(1 for i in range(n) if u16[i] == u16[i+lag]) / n
c16 = []
for lag in range(1, 257):
    c16.append((ac16(lag), lag))
c16.sort(reverse=True)
w("  基线 = 1/65536 ≈ 0.0000153（离散值域下实际远高）")
w("  Top-15 lag(以 u16 为单位):")
for r, lag in c16[:15]:
    w("    lag %3d (=%d B)  →  %.4f" % (lag, lag*2, r))
w()

w("【3】按候选 pitch 分组 · 列取值集中度（表格特征）")
for pitch in (8, 12, 16, 24, 32, 64):
    ncol = pitch
    nrow = N // pitch
    if nrow < 20: continue
    # 每列的取值集中度：中位众数占比
    meds = []
    for c in range(ncol):
        col = [SEG[r*pitch + c] for r in range(nrow)]
        cnt = collections.Counter(col)
        meds.append(cnt.most_common(1)[0][1] / nrow)
    meds.sort()
    w("    pitch %3d  行数 %4d  列众数占比 中位 %.4f  最大 %.4f  (随机期望 %.4f)"
      % (pitch, nrow, meds[len(meds)//2], meds[-1], 1/256))
w()

w("【4】记录假设：pitch 由 c2 f2 锚定")
pat = bytes.fromhex("c2f2")
pos = []
i = 0
while True:
    j = SEG.find(pat, i)
    if j < 0: break
    pos.append(j); i = j + 1
w("  'c2f2' 在 0x1E000 区内出现 %d 次" % len(pos))
if len(pos) > 2:
    d = [pos[k+1]-pos[k] for k in range(len(pos)-1)]
    cd = collections.Counter(d)
    w("  相邻间距统计 Top-10: %s" % ", ".join("%d:%d次" % (k, v) for k, v in cd.most_common(10)))
    w("  间距中位 %d  均值 %.1f" % (sorted(d)[len(d)//2], sum(d)/len(d)))
w()

w("【5】0x1F000 段按 8 字节切，看是否像 (u16 地址, u16 值) 表")
for o in range(0, 0x400, 32):
    base = 0x1F000 + o
    raw = data[base:base+32]
    vals = [int.from_bytes(raw[i:i+2], "little") for i in range(0, 32, 2)]
    w("    0x%05X  %s | %s" % (base, raw.hex(" "),
      " ".join("%5d" % v for v in vals)))
w()

w("【6】与 0x19000 对照（官方 CFG_FLASH_ADDR）")
S2 = data[0x19000:0x1A000]
c2 = []
for lag in range(1, 257):
    if lag >= len(S2): break
    r = sum(1 for i in range(len(S2)-lag) if S2[i] == S2[i+lag]) / (len(S2)-lag)
    c2.append((r, lag))
c2.sort(reverse=True)
w("  0x19000 Top-10 lag: %s" % ", ".join("%d(×%.1f)" % (l, r/0.00390625) for r, l in c2[:10]))
w("  0x19000 最高频字节: %s"
  % ", ".join("0x%02X:%d" % (b, n) for b, n in collections.Counter(S2).most_common(8)))
w("  0x1E000 最高频字节: %s"
  % ", ".join("0x%02X:%d" % (b, n) for b, n in collections.Counter(SEG).most_common(8)))
w()

w("【7】0x1E000 是否含 ASCII / 是否为 TLV")
asc = bytes(sorted(set(b for b in SEG if 0x20 <= b < 0x7f)))
w("  可打印 ASCII 字节种类 %d / 95" % len(asc))
w("  连续 >=4 个可打印字符的串:")
runs = []
cur = b""
for b in SEG:
    if 0x20 <= b < 0x7f:
        cur += bytes([b])
    else:
        if len(cur) >= 4: runs.append(cur)
        cur = b""
if len(cur) >= 4: runs.append(cur)
w("    %s" % (runs[:20] if runs else "无"))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
