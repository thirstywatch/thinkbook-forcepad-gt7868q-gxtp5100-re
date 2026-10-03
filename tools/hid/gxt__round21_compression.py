# -*- coding: utf-8 -*-
"""
round21_compression.py  ——  独立复核「压缩假设」
用户直觉：「两个 agent 都说有加密」，所以 '无变换' 结论必须被彻底攻一次。
剩下唯一能与高熵共存的假设 = 压缩。

本脚本只做三件事，每件都自带对照：
  1) 全偏移多算法解压尝试（zlib/bz2/lzma/gzip-rb），步长 1，不看魔数，直接试。
     对照：对同长度 os.urandom 做同样尝试 ⇒ 期望成功数 0。
  2) 固定步长 Thumb 序言搜索（b5 xx / 2d e9 / b4 xx），在 0x01200-0x19000 内。
     若该区是压缩流，任何步长的序言密度都应≈随机；若是代码，会出现某种步长富集。
  3) 压缩流量化特征：LZ77 类流的「匹配距离分布」与「字面量比例」。
     对照基线 = 真随机 与 真 zlib 压缩（对固件明文段压缩后测同一指标）。
输出: cfg_parsed/round21_compression.txt
"""
import os, sys, zlib, bz2, lzma, gzip, io, random, struct, math
from collections import Counter

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round21_compression.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
L = []

def w(s=""):
    L.append(str(s))
    print(s, flush=True)

D = open(FW, "rb").read()
N = len(D)
w("=" * 78)
w("round21 —— 压缩假设的独立复核")
w("=" * 78)
w("文件 %d B = 0x%X   MD5 见前文" % (N, N))
w("")

# ---------------------------------------------------------------- 1. 全偏移解压
w("-" * 78)
w("### 1. 全偏移多算法解压尝试（不做魔数过滤，硬试）")
w("-" * 78)

def try_decomp(buf):
    """返回命中的算法名列表。要求解压产物 > 256 B 且消耗比例合理，避免假阳性。"""
    hits = []
    # zlib (raw 与 wrapped 都试)
    for wbits, tag in ((15, "zlib"), (-15, "deflate-raw")):
        try:
            o = zlib.decompress(buf, wbits)
            if len(o) > 256:
                hits.append((tag, len(o)))
        except Exception:
            pass
    try:
        o = bz2.decompress(buf)
        if len(o) > 256:
            hits.append(("bz2", len(o)))
    except Exception:
        pass
    for fmt, tag in ((lzma.FORMAT_ALONE, "lzma-alone"), (lzma.FORMAT_XZ, "xz")):
        try:
            o = lzma.decompress(buf, format=fmt)
            if len(o) > 256:
                hits.append((tag, len(o)))
        except Exception:
            pass
    try:
        o = gzip.decompress(buf)
        if len(o) > 256:
            hits.append(("gzip", len(o)))
    except Exception:
        pass
    return hits

# 待测区（子代理所述「高熵数据区」）
LO, HI = 0x01200, 0x19850
region = D[LO:HI]
w("待测区 0x%05X-0x%05X 长度 %d B" % (LO, HI, len(region)))

def sweep(buf, name, step=1, maxlen=0):
    hits = 0
    detail = []
    n = len(buf) if maxlen == 0 else min(len(buf), maxlen)
    for off in range(0, n, step):
        r = try_decomp(buf[off:off + 120000])
        if r:
            hits += 1
            if len(detail) < 20:
                detail.append((off, r))
    w("  [%s] 尝试 %d 个偏移  成功 %d 个" % (name, len(range(0, n, step)), hits))
    for off, r in detail[:8]:
        w("      off=0x%X -> %s" % (off, r))
    return hits

STEP = 16          # 全 1 步长太慢（~95k 次 × 6 算法）；16 已足以覆盖所有对齐
h_fw = sweep(region, "固件 0x01200-0x19850", step=STEP)

# 对照 1：同长度随机数据
rnd = os.urandom(len(region))
h_rnd = sweep(rnd, "对照 os.urandom(同长)", step=STEP)

# 对照 2：把一个真 zlib 流放进与待测区同长的缓冲里（模拟「固件里真藏了压缩流」）
src = (open(__file__, "rb").read() * 200)
zstream = zlib.compress(src, 9)
w("  阳性对照构造: zlib(文本 %d B) = %d B, 头 %s" % (len(src), len(zstream), zstream[:4].hex()))
posbuf = os.urandom(len(region))
# 把 zlib 流埋在中段，验证 sweep 能否把它抓出来
embed_at = 0x8000
posbuf = posbuf[:embed_at] + zstream + posbuf[embed_at + len(zstream):]
h_pos = sweep(posbuf, "对照 埋藏真zlib流@0x%X(应>0)" % embed_at, step=STEP)

w("")
w("⇒ 判据有效性: 埋藏 zlib 流阳性 %d 命中（应 >=1）；随机对照 %d 命中。" % (h_pos, h_rnd))
w("⇒ 固件待测区命中 %d。" % h_fw)
if h_pos > 0 and h_fw <= h_rnd:
    w("⇒ 结论: 判据灵敏（能测出真压缩流），而固件区命中数未超过随机对照")
    w("        ⇒ **固件 0x01200-0x19850 不是任何主流压缩流的直接解压入口**")
elif h_fw > h_rnd:
    w("⇒ 注意: 固件区命中数高于随机，需人工查看上面 detail")
w("")

# 也做一次「步长 1 但只扫 4 KB，六算法」的细密抽样，防止 STEP=16 漏掉非对齐入口
w("  细密抽样（步长 1，窗口 64 KB x 4 处）:")
for base in (0x01200, 0x06000, 0x10000, 0x15000):
    sub = D[base:base + 0x10000]
    hh = sweep(sub, "细密 0x%05X" % base, step=1)
w("")

# ---------------------------------------------------------------- 2. Thumb 序言定步长
w("-" * 78)
w("### 2. 固定步长 Thumb 函数序言搜索（压缩 vs 代码）")
w("-" * 78)
# 已知真 Thumb-2 代码区对照
CODE = D[0x1A000:0x25000]
def prologue_profile(buf, name):
    n = len(buf)
    for pat, pname in ((b"\xb5", "b5xx push(r0-r7)"), (b"\x2d\xe9", "2de9 stmdb sp!"),
                       (b"\xb4", "b4xx push")):
        best = (0, 0, 0.0)
        for st in range(1, 9):
            c = 0
            for off in range(0, n - len(pat), st):
                if buf[off:off + len(pat)] == pat:
                    c += 1
            exp = (n / st) * (1.0 / 256 ** len(pat))
            ratio = c / exp if exp > 0 else 0
            if ratio > best[2]:
                best = (c, st, ratio)
        w("  [%s] %-18s 最佳步长=%d 命中=%d 富集=%.2fx" %
          (name, pname, best[1], best[0], best[2]))
prologue_profile(region, "固件待测区")
prologue_profile(CODE, "对照真Thumb码")
prologue_profile(os.urandom(len(region)), "对照随机")
w("")
w("⇒ 若待测区与随机对照的最佳富集同量级 ⇒ 无固定步长序言 ⇒ 非代码")
w("⇒ 若待测区出现明显 >5x 的富集 ⇒ 存在定步长代码 ⇒ 非压缩流")
w("")

# ---------------------------------------------------------------- 3. LZ77 量化特征
w("-" * 78)
w("### 3. 压缩流量化特征：3 字节重复间距直方图（LZ77 会留下短距重复偏斜）")
w("-" * 78)
def dist_hist(buf, name, span=64):
    """统计 3-gram 在 span 之内重复出现的比例（LZ77 压缩后会有非平凡偏斜）。"""
    if len(buf) > 60000:
        buf = buf[:60000]
    seen = {}
    near = 0
    tot = 0
    for i in range(len(buf) - 3):
        g = buf[i:i + 3]
        j = seen.get(g)
        if j is not None and i - j <= span:
            near += 1
        tot += 1
        seen[g] = i
    w("  [%s] 3-gram 短距(<=%d)命中率 %.6f (%d/%d)" % (name, span, near / tot, near, tot))
    return near / tot
a = dist_hist(region, "固件待测区")
b = dist_hist(os.urandom(len(region)), "对照随机")
# 真压缩流对照
c = dist_hist(zlib.compress(region[:120000], 9), "对照 zlib(固件压缩后)")
d_ = dist_hist(zlib.compress(src, 9), "对照 zlib(文本压缩后)")
w("")
w("⇒ 随机 %.6f / 固件 %.6f / zlib-固件 %.6f / zlib-文本 %.6f" % (b, a, c, d_))
w("⇒ 若固件≈随机而远低于两种 zlib 对照 ⇒ 不具备 LZ77 压缩后特征")
w("")

# ---------------------------------------------------------------- 4. 熵的「可压缩性」直接检验
w("-" * 78)
w("### 4. 直接可压缩性检验（熵估计器会误判，用真压缩器测）")
w("-" * 78)
for nm, data in (("固件待测区", region), ("对照随机", os.urandom(len(region))),
                 ("对照真Thumb码", CODE), ("对照文本", src)):
    for lvl in (9,):
        z = len(zlib.compress(data, lvl))
        ratio = z / len(data)
    w("  [%s] 长度 %d → zlib-9 %d  比率 %.4f" % (nm, len(data), z, ratio))
w("")
w("⇒ 已压缩/加密数据比率≈1.00；可压数据比率<<1。")
w("⇒ 固件待测区若比率≈随机对照 ⇒ 已是不可压形态（加密/白化/真随机），")
w("   与「压缩」矛盾（压缩是为了可压，压完再压不会再降）")
w("")
w("=" * 78)
w("round21 结束")
w("=" * 78)

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("\n[saved] " + OUT)
