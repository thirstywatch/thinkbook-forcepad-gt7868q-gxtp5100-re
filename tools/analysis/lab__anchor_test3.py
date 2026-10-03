"""★★★ 核验：cont 与 GT9896 anchor 是否真的存在长期完全相同的区块（尤其加扰区）？

上一步 B 段显示 cont[0x0122D] 与 anchor[0x000F1] 声称相同 2063 B —— 但这可能是
「长 0 串」造成的伪匹配（两边都有长 0 区，从任意位置对齐都能匹配很久）。
必须独立复核：直接比较固定偏移，不做种子链。

真正的判据：
  若两固件在同一逻辑位置有【相同明文】，则在【加扰区】里它们应也相同
  —— 但加扰区若各自加扰，就不该相同。反之若相同，说明加扰区里存在
     「未被加扰的公共段」（例如共用的厂商常量表）。
  所以先做「不加任何异或」的直比：cont vs anchor 在加扰区的相同率。
"""
import os

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()

print("=" * 78)
print("核验 1：cont[0x0122D:] 与 anchor[0x000F1:] 究竟相同多少？（不设上限）")
print("=" * 78)
ia, ib = 0x0122D, 0x000F1
n = 0
run_start = None
runs = []
while ia + n < len(cont) and ib + n < len(anchor):
    if cont[ia + n] == anchor[ib + n]:
        if run_start is None:
            run_start = n
    else:
        if run_start is not None:
            runs.append((run_start, n - run_start))
            run_start = None
    n += 1
if run_start is not None:
    runs.append((run_start, n - run_start))
runs.sort(key=lambda t: -t[1])
print("  连续相同段的长度谱（top 10）：")
for st, ln in runs[:10]:
    print("     相对 +0x%05X 处，连续 %d B" % (st, ln))
tot = sum(l for _, l in runs)
print("  合计相同 %d B / 比对 %d B = %.4f%%" % (tot, n, 100.0 * tot / n))
print()

print("=" * 78)
print("核验 2：三段区域直比相同率（不加异或）")
print("=" * 78)
zones = [("明文头 0x0000-0x1200", 0x0000, 0x1200),
         ("加扰区 0x1200-0x19800", 0x1200, 0x19800),
         ("TF100A 0x19A00-end", 0x19A00, min(len(cont), len(anchor)))]
for name, s, e in zones:
    if s >= len(anchor) or s >= len(cont):
        print("  %-26s （超出 anchor 长度，跳过）" % name)
        continue
    e2 = min(e, len(anchor), len(cont))
    a, b = cont[s:e2], anchor[s:e2]
    eq = sum(1 for x, y in zip(a, b) if x == y) / len(a)
    print("  %-26s 长度 %6d  相同率 %.4f (=%.1f/256)" % (name, len(a), eq, eq * 256))
print()

print("=" * 78)
print("核验 3：cont 加扰区里能找到多少「anchor 里存在的 ≥16B 片段」？")
print("=" * 78)
SEG = 16
aset = set()
for i in range(0, len(anchor) - SEG):
    aset.add(anchor[i:i + SEG])
hits = []
for j in range(0x1200, min(0x19800, len(cont)) - SEG):
    if cont[j:j + SEG] in aset:
        hits.append(j)
print("  加扰区内命中 %d 个位置（段长 %d）" % (len(hits), SEG))
for j in hits[:20]:
    k = cont[j:j + SEG]
    idx = anchor.find(k)
    print("     cont[0x%05X] == anchor[0x%05X]  %s" % (j, idx, k.hex()))
print()

print("=" * 78)
print("核验 4：锚点偏移 0x7800 附近到底是什么（C 段最高分）？")
print("=" * 78)
for off in (0x7800, 0x7000):
    print("  anchor[0x%05X:0x%05X] 熵与内容" % (off, off + 0x400))
    seg = anchor[off:off + 0x400]
    import collections, math
    c = collections.Counter(seg)
    t = len(seg)
    e = -sum((v / t) * math.log2(v / t) for v in c.values())
    print("     熵=%.4f 0x00占比=%.2f%% 首 32B: %s" % (
        e, 100 * seg.count(0) / t, seg[:32].hex()))
