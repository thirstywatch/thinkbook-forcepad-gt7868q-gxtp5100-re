"""★★★★ 定界实验：GT7868Q「加扰区」里到底哪些部分其实【没有被加扰】？

已确证：
  cont[0x0122D..] 与 anchor[0x000F1..] 有超长逐字节相同（>2000B，熵 7.9）
  cont[0x05638..] 与 anchor[0x0F4FC..] 有 1026B 逐字节相同（熵 6.93）

推论：GT7868Q 与 GT9896 是【同代同族】，固件布局高度共享。
      所谓「加扰区」内部存在大段【与 GT9896 明文完全一致】的区域。

本实验给出【逐段对齐图】：以 anchor 为参照，对 cont 每个位置做
「局部相同率」扫描，画出连续相同/不同的分段边界。

一旦确定「哪些段与明文相同」，就等价于【拿到了这些段的真明文】，
可以直接用于任何后续分析（虽然这些段本身没被加扰，不能解 K，
但它们确定了容器的真实布局 —— 而且若能找到『同一逻辑段在 A 机是明文、
在 B 机是加扰』的证据，就能配对出 K）。

关键额外检验：
  在 cont 的**加扰区**里，找 anchor 中【同一逻辑偏移】是否不同。
  若同偏移同段，一处明文一处密文，则 K = cont_seg ^ anchor_seg 直接得出！
"""
import os
import collections
import math

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


# ── ① 找 best offset：整体平移多少时相同最多 ──
print("=" * 78)
print("① 全局最佳对齐偏移（滑动 anchor 相对 cont）")
print("=" * 78)
best = []
W_IN = 0x2000
for d in range(-0x6000, 0x6000, 0x40):
    # cont[j] vs anchor[j+d]
    lo = max(0, -d)
    hi = min(len(cont), len(anchor) - d)
    if hi - lo < W_IN:
        continue
    seg_c = cont[lo:lo + W_IN]
    seg_a = anchor[lo + d:lo + d + W_IN]
    eq = sum(1 for x, y in zip(seg_c, seg_a) if x == y) / W_IN
    best.append((eq, d))
best.sort(reverse=True)
for eq, d in best[:10]:
    print("   delta=%+6d (0x%X)  相同率 %.4f (=%.2f/256)" % (d, d & 0xFFFF, eq, eq * 256))
print()

# ── ② 逐字节相同率的滑动剖面（最佳 delta 下）──
bdelta = best[0][1]
print("=" * 78)
print("② 在最佳 delta=%+d 下，cont 的逐段相同率剖面（每 4 KiB）" % bdelta)
print("=" * 78)
STEP = 0x1000
for s in range(0, min(len(cont), len(anchor) - bdelta), STEP):
    e = min(s + STEP, len(cont), len(anchor) - bdelta)
    if e - s < 256:
        break
    seg_c = cont[s:e]
    seg_a = anchor[s + bdelta:s + bdelta + (e - s)]
    eq = sum(1 for x, y in zip(seg_c, seg_a) if x == y) / len(seg_c)
    zone = "明文头" if s < 0x1200 else ("加扰区" if s < 0x19800 else "TF100A")
    bar = "#" * int(eq * 100)
    print("   cont 0x%05X (%s)  相同率 %.4f  %s" % (s, zone, eq, bar))
print()

# ── ③ 关键：在「加扰区」内，同偏移段是否真的不同？若不同则能直接得 K ──
print("=" * 78)
print("③ ★ 加扰区内逐段 x 检验：K_seg = cont_seg ⊕ anchor_seg 是否 1024 周期？")
print("=" * 78)
S, E = 0x1200, 0x19800
L = 1024


def rep(x):
    n = len(x) - L
    if n <= 0:
        return None
    return sum(1 for i in range(n) if x[i] == x[i + L]) / n


print("   %-10s %-12s %-10s %s" % ("cont起点", "相同率", "1024周期", "K段熵"))
cand = []
for s in range(0x1200, 0x19800 - 0x2000, 0x1000):
    seg_c = cont[s:s + 0x2000]
    seg_a = anchor[s + bdelta:s + bdelta + 0x2000]
    if len(seg_a) < 0x2000:
        break
    eq = sum(1 for x, y in zip(seg_c, seg_a) if x == y) / len(seg_c)
    k = bytes(a ^ b for a, b in zip(seg_c, seg_a))
    r = rep(k)
    print("   0x%05X    %.4f       %s    %.4f" % (
        s, eq, ("%.6f" % r) if r is not None else "n/a", ent(k)))
    if r is not None and r > 0.05:
        cand.append((r, s))
print()
if cand:
    print("   ★★ 有段落的 K 呈现 1024 周期！")
    for r, s in sorted(cand, reverse=True):
        print("      cont 0x%05X  K 周期一致性 %.6f" % (s, r))
else:
    print("   （无段落呈现 1024 周期 —— 说明 anchor 与 cont 的对应段不同源）")
