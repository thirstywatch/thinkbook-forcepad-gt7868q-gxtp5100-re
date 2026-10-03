# -*- coding: utf-8 -*-
"""
round22_residual.py —— 「0.8797 可压比」来源分解
round21 实测：0x01200-0x19850 用 zlib-9 压后比率 0.8797（随机=1.0004，真Thumb码=0.4719）。
这个 12% 的富余不是噪声 —— 它是判断「该区到底是什么」的最强单一数字。
本脚本把 0.8797 分解到具体原因：
  A) 它是不是「块间重复」造成的？把重复块剔除后再测比率。
  B) 它是不是「字节分布偏斜」造成的？做字节直方图熵 vs 一阶马尔可夫熵。
  C) 它是不是「局部周期性」造成的？对不同 lag 做互信息/自相关。
  D) 与「同长度真随机但注入 X% 重复」对照，反推等效重复量。
输出: cfg_parsed/round22_residual.txt
"""
import os, zlib, math, random
from collections import Counter

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round22_residual.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
L = []
def w(s=""):
    L.append(str(s)); print(s, flush=True)

D = open(FW, "rb").read()
LO, HI = 0x01200, 0x19850
R = D[LO:HI]
CODE = D[0x1A000:0x25000]
w("=" * 78)
w("round22 —— 0.8797 可压比的来源分解")
w("=" * 78)
w("待测区 0x%05X-0x%05X  %d B" % (LO, HI, len(R)))
w("")

def ratio(b):
    return len(zlib.compress(b, 9)) / len(b)

# ---------------------------------------------------------------- A) 重复块剔除
w("-" * 78)
w("### A. 重复块贡献：找出所有重复的 512 B 块，只留唯一副本后重测")
w("-" * 78)
BS = 512
blocks = [R[i:i + BS] for i in range(0, len(R) - BS + 1, BS)]
seen = {}
uniq = []
dup_bytes = 0
for idx, b in enumerate(blocks):
    h = b  # 512 B 直接做 dict key
    if h in seen:
        dup_bytes += BS
    else:
        seen[h] = idx
        uniq.append(b)
uniq_data = b"".join(uniq)
w("  512B 块总数 %d, 唯一 %d, 重复字节 %d (%.2f%%)" %
  (len(blocks), len(uniq), dup_bytes, 100.0 * dup_bytes / len(R)))
w("  原始比率 %.4f" % ratio(R))
w("  去重后比率 %.4f (对 %d B)" % (ratio(uniq_data), len(uniq_data)))
# 对照：同样长度随机
rnd = os.urandom(len(R))
w("  对照随机比率 %.4f" % ratio(rnd))
w("")
w("  ⇒ 若去重后比率仍显著 < 随机 ⇒ 0.8797 不是（只）由块重复造成")
w("")

# ---------------------------------------------------------------- B) 一阶 vs 零阶熵
w("-" * 78)
w("### B. 字节分布偏斜 vs 一阶转移：熵分解（单位 bit/byte）")
w("-" * 78)
def h0(b):
    c = Counter(b); n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())
def h1(b):
    c = Counter(zip(b[:-1], b[1:])); n = len(b) - 1
    return -sum((v / n) * math.log2(v / n) for v in c.values())
def h2(b):
    c = Counter(zip(b[:-2], b[1:-1], b[2:])); n = len(b) - 2
    return -sum((v / n) * math.log2(v / n) for v in c.values())
def hmc(b):
    """一阶马尔可夫熵（条件熵）= H1 - H0，反映「给定前字节后的不确定性」"""
    return h1(b) - h0(b)
for nm, b in (("待测区", R), ("随机", os.urandom(len(R))), ("真Thumb码", CODE)):
    w("  [%s] H0=%.4f  H1=%.4f  H2=%.4f  条件熵H1-H0=%.4f" % (nm, h0(b), h1(b), h2(b), hmc(b)))
w("")
w("  ⇒ H0 明显 < 8 说明字节分布有偏斜（可能来自填充/表/文本）")
w("  ⇒ 条件熵 ≈ 8 说明「字节间无依赖」，即无序列相关、无置换、无周期")
w("  ⇒ 若条件熵 ≈ 7.99 但 H0 ≈ 7.9 ⇒ 只是字符集偏斜，不是结构")
w("")

# ---------------------------------------------------------------- B2) 直方图 Top
w("  --- 待测区字节直方图 Top20 ---")
c = Counter(R)
for byte, cnt in c.most_common(20):
    w("      0x%02X : %6d  (%.4f%%)" % (byte, cnt, 100.0 * cnt / len(R)))
w("")

# ---------------------------------------------------------------- C) 周期自相关
w("-" * 78)
w("### C. 局部周期性：lag 上的相等率（同字节对同位置比对）")
w("-" * 78)
def lag_eq(b, lag):
    a = b[:-lag]; d = b[lag:]
    same = sum(1 for x, y in zip(a, d) if x == y)
    return same / len(a)
w("  随机期望 1/256 = 0.003906")
for lag in (1, 2, 4, 8, 16, 64, 256, 512, 1024, 2048, 4096):
    e = lag_eq(R, lag)
    w("    lag=%-6d 相等率 %.5f  (随机倍数 %.2fx)" % (lag, e, e / 0.00390625))
w("  --- 对照随机 ---")
rr = os.urandom(len(R))
for lag in (1, 2, 4, 8, 1024):
    e = lag_eq(rr, lag)
    w("    lag=%-6d 相等率 %.5f  (随机倍数 %.2fx)" % (lag, e, e / 0.00390625))
w("")

# ---------------------------------------------------------------- D) 等效重复量反推
w("-" * 78)
w("### D. 等效重复量反推：在随机基线上注入 X% 的 512B 复制块，匹配 0.8797")
w("-" * 78)
def synth(n, dup_frac):
    """生成 n 字节：dup_frac 比例的块是前面块的复制，其余随机。"""
    out = bytearray()
    nblk = n // BS
    src = [os.urandom(BS) for _ in range(nblk)]
    ndup = int(nblk * dup_frac)
    pick = set(random.sample(range(nblk), ndup))
    for i in range(nblk):
        if i in pick and i > 0:
            out += out[(i - 1) * BS:(i - 1) * BS + BS]   # 复制前一块
        else:
            out += src[i]
    return bytes(out)
w("  注入比例 -> zlib比率（各测 3 次取均）")
for f in (0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30):
    rs = [ratio(synth(len(R), f)) for _ in range(3)]
    w("    %5.1f%%  -> %.4f" % (100 * f, sum(rs) / len(rs)))
w("")
w("  ⇒ 与实测 0.8797 对照，反推该区「等效 512B 块重复率」")
w("  ⇒ 同时注意：合成样本的 H0 恒为 8.0，若实测 H0 < 8，")
w("     则重复只解释一部分，剩余来自分布偏斜")
w("")
w("=" * 78)
w("round22 结束")
w("=" * 78)
open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("\n[saved] " + OUT)
