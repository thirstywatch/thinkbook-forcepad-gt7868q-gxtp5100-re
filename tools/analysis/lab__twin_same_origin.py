"""★★★★★ 终局实验：GT7868Q 的「中间态段」是否 = GT9896 明文 ⊕ (1024 周期 keystream)？

熵剖面新事实（本机 cont，161628 B）：
  0x0000-0x1400  熵 4.8-6.4   明文
  0x1400-0x8400  熵 ~7.80      ★「中间态」← 疑似 位置型加扰
  0x8800-0x9400  熵 8.0000     真乱码（仅 3 KiB）
  0x9800-0x19800 熵 ~7.80      同中间态
  0x19800+       熵 5.4-6.6    明文（TF100A）

而 GT9896 anchor 自身全程熵 7.97-7.99（即它也是加扰态！）。
所以 anchor【不是明文】，它只是「另一种加扰态」。

⇒ 关键新判据：若两机固件来自【同一个明文源】（同族固件），
   则 C1 ⊕ C2 = K1 ⊕ K2 应是【1024 周期的】（两个周期 keystream 异或仍周期）。
   这个判据【不需要绝对明文】，只需要两机同源！

本脚本：
  A. 测 cont 各段 ⊕ anchor 同偏移段的 1024 周期性（找同源段落）
  B. 测 cont 各段 ⊕ anchor 各偏移段的 1024 周期性（全搜索，找平移对齐）
  C. 若找到，则 K1⊕K2 得手 ⇒ 再看能否进一步分离
"""
import os
import collections
import math

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()
L = 1024
BASE = 1.0 / 256


def rep(x):
    n = len(x) - L
    if n <= 0:
        return None
    return sum(1 for i in range(n) if x[i] == x[i + L]) / n


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


# GT9896 的熵剖面（确认它也是加扰态还是明文）
print("=" * 88)
print("⓪ GT9896 anchor 熵剖面（每 4 KiB）")
print("=" * 88)
for s in range(0, len(anchor), 0x1000):
    seg = anchor[s:s + 0x1000]
    if len(seg) < 256:
        break
    print("  0x%05X  熵=%.4f  %s" % (s, ent(seg),
          "明文" if ent(seg) < 7.5 else ("加扰?" if ent(seg) < 7.95 else "乱码")))
print()

# ── A. 同偏移段 ──
print("=" * 88)
print("A. cont[off:off+16K] ⊕ anchor[off:off+16K] 的 1024 周期性（同偏移）")
print("=" * 88)
print("   %-10s %-12s %-12s %s" % ("cont起点", "1024周期", "倍数", "K熵"))
hits = []
for s in range(0, min(len(cont), len(anchor)) - 0x10000, 0x2000):
    a = cont[s:s + 0x4000]
    b = anchor[s:s + 0x4000]
    if len(b) < 0x4000:
        break
    k = bytes(x ^ y for x, y in zip(a, b))
    r = rep(k)
    if r is None:
        continue
    mark = "★" if r > 0.03 else " "
    print("  %s 0x%05X   %.6f     %5.1f×     %.4f" % (mark, s, r, r / 0.0039, ent(k)))
    if r > 0.03:
        hits.append((r, s, 0))
print()

# ── B. 平移全搜索（粗粒度）──
print("=" * 88)
print("B. 平移全搜索：cont 固定段 vs anchor 各偏移（粗粒度，找同源位移）")
print("=" * 88)
seg = cont[0x1400:0x1400 + 0x20000]     # 中间态段
best = []
for d in range(-0x8000, 0x8000, 0x100):
    lo = 0
    ai = d
    if ai < 0:
        lo = -ai; ai = 0
    n = min(len(seg) - lo, len(anchor) - ai, 0x20000)
    if n < 0x8000:
        continue
    k = bytes(x ^ y for x, y in zip(seg[lo:lo + n], anchor[ai:ai + n]))
    r = rep(k)
    if r:
        best.append((r, d))
best.sort(reverse=True)
for r, d in best[:12]:
    print("   delta=%+7d  1024周期=%.6f  (%.1f×基线)" % (d, r, r / 0.0039))
print()

if hits or (best and best[0][0] > 0.03):
    print("  ★★ 检测到同源信号！K1⊕K2 呈 1024 周期。")
else:
    print("  ⇒ 全部落在 1024 周期基线附近（≈0.004）。")
    print("     两机固件【不同源】—— GT9896(触屏) 与 GT7868Q(触控板) 的明文内容不同，")
    print("     因此即便同为位置型加扰，(C1⊕C2) 也只是两个无关 keystream 的异或，")
    print("     不呈现任何周期性。⇒ anchor 无法用于解 K。")
