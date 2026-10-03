# vib_table.py — 解码镜像尾部前的 1.7KB 数据表 0x0800D600..0x0800DCA0：是不是 LRA 波形库？
import struct, math, io
BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
img = open(BIN, "rb").read()[0x19ABC:]
BASE = 0x08000000
A, B = 0x0800D600, 0x0800DCA0
blk = img[A - BASE:B - BASE]
out = io.open(r"<LAB>\touchpad-lab\re\vib_table_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

P("区间 0x%08X..0x%08X  长度 %d 字节" % (A, B, len(blk)))

# 1) 熵 + 字节直方图摘要
def ent(b):
    if not b: return 0
    h = [0] * 256
    for x in b: h[x] += 1
    n = len(b)
    return -sum((c / n) * math.log(c / n, 2) for c in h if c)
P("整体熵 = %.3f b/B" % ent(blk))
for s in range(0, len(blk), 256):
    e = blk[s:s + 256]
    P("  +0x%04X 熵 %.2f  首字节 %s" % (s, ent(e), " ".join("%02X" % x for x in e[:12])))

# 2) 当 u16 LE 样本看
u = struct.unpack("<%dH" % (len(blk) // 2), blk[:len(blk) // 2 * 2])
P("\n[u16 LE] n=%d  min=0x%04X max=0x%04X 均值=%.1f  唯一值=%d" % (len(u), min(u), max(u), sum(u) / len(u), len(set(u))))
from collections import Counter
c = Counter(u)
P("  出现最多的 12 个值: " + ", ".join("0x%04X×%d" % (v, k) for v, k in c.most_common(12)))
# 自相关（找波形周期）
n = len(u); mu = sum(u) / n
var = sum((x - mu) ** 2 for x in u) / n
if var > 0:
    best = []
    for lag in range(1, 65):
        s = sum((u[i] - mu) * (u[i + lag] - mu) for i in range(0, n - lag)) / (n - lag)
        best.append((s / var, lag))
    best.sort(reverse=True)
    P("  自相关最强的前 6 个 lag: " + ", ".join("lag=%d r=%.3f" % (l, r) for r, l in best[:6]))
# 零游程
runs = []
cur = 0
for x in u:
    if x == 0: cur += 1
    elif cur: runs.append(cur); cur = 0
if cur: runs.append(cur)
P("  0 值游程: %d 段, 最长 %s, 前 10 段 %s" % (len(runs), max(runs) if runs else 0, runs[:10]))

# 3) 当 u32 LE 看（表头/偏移表？）
w = struct.unpack("<%dI" % (len(blk) // 4), blk[:len(blk) // 4 * 4])
P("\n[u32 LE] 前 24 个: " + " ".join("%08X" % x for x in w[:24]))
inimg = [i for i, x in enumerate(w) if BASE <= x < BASE + len(img)]
P("  落在镜像地址区间内的 u32: %d 个 %s" % (len(inimg), inimg[:10]))
near = [i for i, x in enumerate(w) if 0x08000000 <= x < 0x08020000]
P("  落在 0x0800xxxx 的 u32: %d 个 前 10: %s" % (len(near), [("%08X" % w[i]) for i in near[:10]]))

# 4) 逐字节 ASCII 观感
asc = "".join(chr(b) if 32 <= b < 127 else "." for b in blk)
P("\n[ASCII 观感 前 256 字节]\n" + asc[:256])
out.close()
print("done")
