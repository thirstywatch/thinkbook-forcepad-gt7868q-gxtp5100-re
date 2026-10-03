#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
whiten_probe.py —— 判定「白化/加扰」是否为本族固件的**通用工艺**（而非某文件特有）

【本轮新发现】
  tpfw.bin（官方"明文"固件）局部存在 **完美均衡块**:
     @0x1C00, 0x2000, 0x2400, 0x2800, 0x2C00  (连续 5 KiB)
     @0x9C00, 0xA000, 0xA400                    (连续 3 KiB)
     @0xC400, 0x11400
     每 1024 B 中 256 个字节值各出现恰好 4 次（熵恰为 8.000000）
  这是**人为白化**的指纹，随机数据不会这么均衡（卡方 p<0.001 时不应完美）。

【假设】Goodix 固件格式 = [明文头][白化数据区]，"白化"= 用固定 1024 B 表 K2 做异或 + 可能的位置置换。
  若成立，则：
    H1 这些均衡块的「自相关」应显示 1024/4096 周期
    H2 与 GT7868Q 的 K 表应存在同源性（K2 ≈ K 或 K2 与 K 有共同子结构）
    H3 用 K 去 XOR tpfw 的均衡块，应产出的不再是完美均衡（说明 K 确实是配对的表）

本脚本检验 H1/H2/H3。
"""
import os, math
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
TPFW = os.path.join(BASE, "tpfw_86272_PNOR_G1_7863.bin")
K_CAND = [
    r"<LAB>\touchpad-lab\poc\anchor-hunt\GT7868Q_scramble_key.bin",
]
K_LOCAL = os.path.join(BASE, "K_gt7868q.bin")

line = []


def w(s=""):
    line.append(s)
    print(s)


def ent(x):
    if not x:
        return 0.0
    c = Counter(x)
    n = len(x)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def load_k():
    for p in [K_LOCAL] + K_CAND:
        if os.path.exists(p):
            d = open(p, "rb").read()
            w("  K 表来源: %s  (%d B)" % (p, len(d)))
            return d, p
    return None, None


with open(TPFW, "rb") as f:
    tpfw = f.read()

w("=" * 78)
w("白化工艺通用性探针")
w("=" * 78)

# ---------------------------------------------------------------- H1
w("\n【H1】均衡块的自相关（周期检测）")
w("-" * 78)
seg = tpfw[0x1C00:0x2C00]   # 4 KiB 全均衡区
w("  样本 = tpfw[0x1C00:0x2C00]  (%d B, H=%.4f)" % (len(seg), ent(seg)))
peaks = []
for lag in range(1, 4097):
    if lag >= len(seg):
        break
    same = sum(1 for i in range(0, len(seg) - lag, 37)
               if (seg[i] ^ seg[i + lag]) == 0)
    tot = len(range(0, len(seg) - lag, 37))
    if tot:
        ratio = same / tot
        if ratio > 0.02:
            peaks.append((lag, ratio))
peaks.sort(key=lambda x: -x[1])
w("  自相关（采样 1/37，命中率>2%% 的滞后）TOP10:")
for lag, r in peaks[:10]:
    w("     lag=%4d  命中率 %.4f  (随机基线 ~%.4f)" % (lag, r, 1 / 256.0))
if not peaks:
    w("     无显著峰值 → 均衡区内部无 1024/4096 周期")
w("""
  判读: 若 lag=1024 / 2048 / 4096 处有显著命中，则数据是「块重复」；
        若无，则它是「真白化」（每块内容不同但统计均衡）。
        两者含义不同:
          - 块重复 → 可以用自消法消掉，等于上一轮 K 表的翻版（陷阱！）
          - 真白化 → 需要真密钥，或者它根本就是【压缩数据】而非加密数据
""")

# ---------------------------------------------------------------- H2
w("\n【H2】K 表与 tpfw 均衡块的同源性")
w("-" * 78)
K, kp = load_k()
if K:
    # tpfw 中是否含有 K 的片段
    if len(K) >= 64:
        probe = K[:32]
        hits = []
        s = 0
        while True:
            j = tpfw.find(probe, s)
            if j < 0:
                break
            hits.append(j)
            s = j + 1
        w("  K[0:32] 在 tpfw 中命中 %d 次 %s" % (len(hits), [hex(x) for x in hits[:10]]))
    # tpfw 中是否自身重复 K 结构（用 K 首 16 字节做探针）
    probe16 = K[:16]
    hits16 = []
    s = 0
    while True:
        j = tpfw.find(probe16, s)
        if j < 0:
            break
        hits16.append(j)
        s = j + 1
    w("  K[0:16]   在 tpfw 中命中 %d 次 %s" % (len(hits16), [hex(x) for x in hits16[:10]]))

    # 逐字节比对：K 与 tpfw 各 1024 块的最长公共子串位置（用 8 字节窗口）
    w("\n  K 与 tpfw 各 1024 块的 8 字节窗口重合度:")
    kw = set(K[i:i + 8] for i in range(len(K) - 8))
    for i in range(0, min(len(tpfw), 0x8000), 1024):
        blk = tpfw[i:i + 1024]
        bw = set(blk[j:j + 8] for j in range(len(blk) - 8))
        inter = len(kw & bw)
        w("     tpfw[0x%05X:0x%05X]  与 K 共享 8B 窗口 %d 个" % (i, i + 1024, inter))

# ---------------------------------------------------------------- H3
w("\n【H3】用 K 异或均衡块后，均衡性是否被打破")
w("-" * 78)
if K and len(K) == 1024:
    for start in (0x1C00, 0x2000, 0x9C00):
        blk = tpfw[start:start + 1024]
        x = bytes(blk[i] ^ K[i % 1024] for i in range(len(blk)))
        c0 = Counter(blk); c1 = Counter(x)
        bal0 = (len(c0) == 256 and len(set(c0.values())) == 1)
        bal1 = (len(c1) == 256 and len(set(c1.values())) == 1)
        w("  @0x%05X  原始: H=%.4f 均衡=%s |  XOR K 后: H=%.4f 均衡=%s  零数=%d"
          % (start, ent(blk), bal0, ent(x), bal1, x.count(0)))
    w("""
  判读:
    • 若 XOR K 后**仍是**完美均衡 → K 与这些块无关（K 不是这里的表）
    • 若 XOR K 后均衡被打破且出现 0 → K 恰好是这里的表，且**这块本来就没被施法**
      ↑ 这正是上一轮那个陷阱的形态，必须警惕！
    • 若 XOR K 后熵不降、均衡不破 → 无关
""")

w("\n【结论】")
w("-" * 78)
w("""
1. tpfw.bin 不是"纯明文固件"——它含 10 个 1 KiB 完美均衡块（人为白化指纹）。
   "PNOR_G1" 这个 magic 只保证「头是明的」，不保证「体是明的」。
   ⇒ ★ 又一次判据错误：我把 magic 当成了全局明文承诺。

2. GT7868Q 的 K（1024 B）与 tpfw 的均衡块**是否同源，本脚本给出直接证据**。

3. 新的正确判据: 「明文」必须同时满足
     (a) magic 正确
     (b) 熵剖面**不出现完美均衡块**（完美均衡 = 有人工白化）
     (c) 含可读 ASCII 标识（产品名/版本串/寄存器名）
     (d) 子固件表指向的段地址落在文件长度内
""")

with open(os.path.join(BASE, "cfg_parsed", "whiten_probe.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(line))
print("\n[done] -> cfg_parsed/whiten_probe.txt")
