# -*- coding: utf-8 -*-
"""
0x1E000 记录结构解码（继续研究）
 0. 先验证"3 字节头"假设：c2 f2 之外的其它头变体（c2 f6? 44 f2?）
 1. 按"记录头"切分，统计每条记录长度
 2. 每条记录内部字段渲染（u8/u16 视图）
 3. 与官方源码的 GT7868Q cfg 结构体做语义联想
"""
import os, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "region_1E000_records.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

SEG = data[0x1E000:0x20000]
N = len(SEG)
w("=" * 80)
w("0x1E000 记录结构解码")
w("=" * 80); w()

w("【0】候选记录头模式的全扫描（3 字节头假设）")
# 找所有形如 XX YY 00 / XX YY 01 的三字节串，统计 XX YY 的分布
c3 = collections.Counter(SEG[i:i+3] for i in range(N-2))
w("  3 字节串 Top-25:")
for k, v in c3.most_common(25):
    w("    %s  ×%d" % (k.hex(" "), v))
w()

w("【0b】把所有高频 2 字节作为候选头，看其后继确定度")
c2 = collections.Counter(SEG[i:i+2] for i in range(N-1))
for k, v in c2.most_common(24):
    if v < 20: continue
    nxt = collections.Counter(SEG[i+2] for i in range(N-1) if SEG[i:i+2] == k and i+2 < N)
    tot = sum(nxt.values())
    top = nxt.most_common(3)
    w("    %s ×%-4d  后继: %s  (确定度 %.3f)"
      % (k.hex(" "), v, ", ".join("0x%02X:%d" % (b, n) for b, n in top), top[0][1]/tot))
w()

w("【1】用 c2 f2 作分隔符切分记录（把 c2 f2 视为记录起始）")
pos = [i for i in range(N-1) if SEG[i:i+2] == b"\xc2\xf2"]
w("  c2 f2 位置数 %d，首 0x%X，末 0x%X" % (len(pos), pos[0], pos[-1]))
segs = []
for k in range(len(pos)-1):
    segs.append(SEG[pos[k]:pos[k+1]])
w("  切出 %d 段，长度分布（Top-20）:" % len(segs))
cl = collections.Counter(len(s) for s in segs)
w("    %s" % ", ".join("%d:%d" % (l, n) for l, n in cl.most_common(20)))
w()

w("【2】短记录（<=32 B）逐条渲染")
short = [s for s in segs if len(s) <= 32]
w("  共 %d 条短记录，前 25 条:" % len(short))
for s in short[:25]:
    u16 = [int.from_bytes(s[i:i+2], "little") for i in range(0, len(s)-1, 2)]
    w("    [%2dB] %-46s  u16: %s" % (len(s), s.hex(" "), " ".join("%5d" % v for v in u16)))
w()

w("【3】忽略头，看体的字段布局：取最常见的记录长度")
common_len = cl.most_common(1)[0][0]
w("  最常见记录长度 = %d B" % common_len)
same = [s for s in segs if len(s) == common_len]
w("  共 %d 条。按列统计每字节位置的取值集中度:" % len(same))
w("      pos  众数值  占比   次高")
for c in range(common_len):
    col = [s[c] for s in same]
    cc = collections.Counter(col)
    top = cc.most_common(2)
    w("      +%2d  0x%02X   %.3f   %s" % (c, top[0][0], top[0][1]/len(col),
      ", ".join("0x%02X:%d" % (b, n) for b, n in top[1:])))
w()

w("【4】把 0x1E000 按 16 位对齐整体渲染（前 512 u16），标注高频操作数")
u16all = [int.from_bytes(SEG[i:i+2], "little") for i in range(0, N-1, 2)]
w("  16 位值 Top-30 (值, 次数, 若交换字节后的首字节):")
c16 = collections.Counter(u16all)
for v, n in c16.most_common(30):
    lo = v & 0xFF; hi = (v >> 8) & 0xFF
    w("    0x%04X ×%-4d  字节 %02X %02X   高字节 0x%02X" % (v, n, lo, hi, hi))
w()

w("【5】检查是否有 0x5A / 0x1E000 里是否含 I²C 地址 0x5A (AW86927 可能地址)")
for addr in (0x5A, 0x5B, 0x58, 0x59):
    n = SEG.count(addr)
    exp = N / 256
    w("    0x%02X : 出现 %4d 次  (随机期望 %.1f, 富集 ×%.1f)" % (addr, n, exp, n/exp))
w()

w("【6】0x1E000 与 0x19000（另一活配置区）的相似度")
S2 = data[0x19000:0x1A000]
same_bytes = sum(1 for i in range(4096) if SEG[i] == S2[i])
w("  逐字节相同（同偏移）: %d / 4096 = %.3f" % (same_bytes, same_bytes/4096))
c1 = collections.Counter(SEG[:4096]); c2b = collections.Counter(S2)
dot = sum(c1[b]*c2b[b] for b in set(c1) | set(c2b))
import math
n1 = sum(c1.values()); n2 = sum(c2b.values())
# 余弦相似度
num = sum(c1[b]*c2b[b] for b in range(256))
d1 = math.sqrt(sum(v*v for v in c1.values())); d2 = math.sqrt(sum(v*v for v in c2b.values()))
w("  字节直方图余弦相似度: %.4f" % (num/(d1*d2)))
w()

w("【7】0x1E000 是否可能是波形/系数表：看数值序列的平滑性（相邻 u16 差）")
diffs = collections.Counter()
for i in range(0, N-3, 2):
    a = int.from_bytes(SEG[i:i+2], "little")
    b = int.from_bytes(SEG[i+2:i+4], "little")
    diffs[b-a] += 1
w("  相邻 u16 差值 Top-12: %s" % ", ".join("%d:%d" % (k, v) for k, v in diffs.most_common(12)))
w("  ⇒ 若差值高度集中在 0/±1/±2 ⇒ 平滑数据（波形/系数）；若散乱 ⇒ 结构化记录")
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
