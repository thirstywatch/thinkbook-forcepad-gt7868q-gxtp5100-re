"""★★★★★★ 终极实验：从「纯 1024 周期区」提取 K，验证是否为全局共用密钥。

发现：
  cont   [0x08400..0x08A00]  1024 自相关 = 1.000000，熵 8.0
  anchor [0xD800..0xE800]    1024 自相关 = 1.000000，熵 8.0

假设：这些区域明文为常量（全 0），故 C ≡ K（循环移位），直接暴露 K。

验证链：
  1. 精确定界「纯周期区」
  2. 提取两个 K 候选，比对（含全部 1024 种循环移位）
  3. 用 K 解 cont 整个加扰区，测明文熵是否显著下降
  4. 用同一 K 解 anchor，交叉验证
  5. 判据：若解出的明文熵显著 < 8.0 且出现可读结构 ⇒ K 正确
"""
import os
import collections
import math

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()
L = 1024


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


def pure_runs(d, thresh=0.999):
    """找出「整块 1024 与下一块 1024 完全相同」的连续区间"""
    runs = []
    cur = None
    for off in range(0, len(d) - 2 * L):
        same = d[off:off + L] == d[off + L:off + 2 * L]
        if same:
            if cur is None:
                cur = off
        else:
            if cur is not None:
                runs.append((cur, off))
                cur = None
    if cur is not None:
        runs.append((cur, len(d) - 2 * L))
    # 合并间隔 < 64 的
    merged = []
    for s, e in runs:
        if merged and s - merged[-1][1] < 64:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return [(s, e) for s, e in merged if e - s > 256]


print("=" * 90)
print("① 纯 1024 周期区定界")
print("=" * 90)
runs_c = pure_runs(cont)
runs_a = pure_runs(anchor)
print("  cont   纯区 %d 段：" % len(runs_c))
for s, e in runs_c:
    print("     0x%05X - 0x%05X  (%d B)" % (s, e, e - s))
print("  anchor 纯区 %d 段：" % len(runs_a))
for s, e in runs_a:
    print("     0x%05X - 0x%05X  (%d B)" % (s, e, e - s))
print()

# 取每个文件最长纯区的中段作为 K 候选（避免边界不齐）
def pick_k(d, runs, name):
    if not runs:
        return None, None
    s, e = max(runs, key=lambda t: t[1] - t[0])
    mid = s + 2048
    if mid + L > len(d):
        mid = s
    k = d[mid:mid + L]
    print("  %s 取 K 候选 @0x%05X  熵=%.4f" % (name, mid, ent(k)))
    return k, mid


print("=" * 90)
print("② K 候选提取")
print("=" * 90)
kc, oc = pick_k(cont, runs_c, "cont  ")
ka, oa = pick_k(anchor, runs_a, "anchor")
print()

print("=" * 90)
print("③ 两个 K 候选是否相同（含全部 1024 种循环移位）")
print("=" * 90)
if kc and ka:
    best = []
    for rot in range(L):
        krot = ka[rot:] + ka[:rot]
        eq = sum(1 for x, y in zip(kc, krot) if x == y) / L
        best.append((eq, rot))
    best.sort(reverse=True)
    for eq, rot in best[:5]:
        print("   cont_K vs anchor_K<<%4d : 相同率 %.4f (=%.2f/256)" % (rot, eq, eq * 256))
    print()
    if best[0][0] > 0.9:
        print("   ★★★ 两个 K 候选实质相同！⇒ K 是 GTX8 全局共用的固定表。")
    elif best[0][0] > 0.01:
        print("   ? 有弱相关，需进一步验证。")
    else:
        print("   ⇒ 两个 K 候选无关（各自是独立的 1024 周期序列）。")
print()

print("=" * 90)
print("④ 决定性测试：用 K 解扰，明文熵是否下降？")
print("=" * 90)


def decode_stats(d, K, s, e, phase=0):
    seg = d[s:e]
    n = len(seg)
    p = bytes(seg[i] ^ K[(i + phase) % L] for i in range(n))
    return ent(p), p


# 对照：用随机 K
import random
random.seed(3)
Krand = bytes(random.randrange(256) for _ in range(L))

S, E = 0x1400, 0x19800
print("  取样段 cont[0x%05X:0x%05X]" % (S, E))
e_rand, _ = decode_stats(cont, Krand, S, min(S + 0x4000, E))
print("     用【随机 K】解扰：明文熵 = %.4f  （基准，若 K 无效应仍 ~8.0）" % e_rand)
if kc:
    # 对 1024 种相位测（因为不知道 K 的相位对齐）
    res = []
    for ph in range(L):
        ev, _ = decode_stats(cont, kc, S, min(S + 0x4000, E), ph)
        res.append((ev, ph))
    res.sort()
    print("     用【自身 K 候选】解扰：最佳相位 %d 明文熵 = %.4f （最差 %.4f）" % (
        res[0][1], res[0][0], res[-1][0]))
if ka:
    res2 = []
    for ph in range(L):
        ev, _ = decode_stats(cont, ka, S, min(S + 0x4000, E), ph)
        res2.append((ev, ph))
    res2.sort()
    print("     用【GT9896 K 候选】解扰：最佳相位 %d 明文熵 = %.4f （最差 %.4f）" % (
        res2[0][1], res2[0][0], res2[-1][0]))
print()

# ── ⑤ 直接看：纯区里两块是否真的相同（人眼核验）──
print("=" * 90)
print("⑤ 纯区原始字节（人眼核验「真周期」）")
print("=" * 90)
if runs_c:
    s, e = max(runs_c, key=lambda t: t[1] - t[0])
    print("  cont 0x%05X 前 96B :" % s)
    print("    ", cont[s:s + 96].hex())
    print("    ", cont[s + L:s + L + 96].hex())
    print("    两块相同? %s" % (cont[s:s + L] == cont[s + L:s + 2 * L]))
if runs_a:
    s, e = max(runs_a, key=lambda t: t[1] - t[0])
    print("  anchor 0x%05X 前 96B :" % s)
    print("    ", anchor[s:s + 96].hex())
    print("    ", anchor[s + L:s + L + 96].hex())
    print("    两块相同? %s" % (anchor[s:s + L] == anchor[s + L:s + 2 * L]))
