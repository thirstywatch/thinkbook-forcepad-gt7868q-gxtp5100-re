"""★★★★★ 寻找「K 泄露点」：明文为常量填充（全 0/全 FF）的段落会把 K 直接暴露出来。

原理：C[i] = P[i] ⊕ K[i % 1024]
      若某段 P 全为常量 v（0x00 或 0xFF 等），则 C ≡ v ⊕ K
      ⇒ 该段内 C[i] == C[i+1024] 恒成立（100%），因为 K 以 1024 为周期！
      反之，随机明文段的该比例只有 ~0.39%。

所以：扫描加扰区，找 1024 自相关接近 1.0 的窗口。找到即得 K。

同时测：哪一段的明文在 1024 尺度上最高重复。

输入：cont（GT7868Q 容器）与 GT9896 anchor，两者都是 1024 周期加扰态。
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


def scan(name, d, zones):
    print("=" * 88)
    print("扫描 %s（%d B）" % (name, len(d)))
    print("=" * 88)
    print("  %-12s %-10s %-8s %-8s %s" % ("偏移", "1024自相关", "倍数", "段熵", "备注"))
    found = []
    WIN = L * 4          # 4096 B 窗口
    STEP = 256
    for zone_name, s, e in zones:
        e = min(e, len(d))
        for off in range(s, e - WIN, STEP):
            w = d[off:off + WIN]
            n = len(w) - L
            hit = sum(1 for i in range(n) if w[i] == w[i + L])
            r = hit / n
            if r > 0.20:
                found.append((r, off, zone_name, ent(w)))
    found.sort(reverse=True)
    if not found:
        print("   （无任何窗口 1024 自相关 > 0.20）")
    for r, off, zn, ev in found[:20]:
        print("  0x%05X    %.6f   %6.1f×   %.4f   %s" % (off, r, r / 0.0039, ev, zn))
    print()
    return found


zones_cont = [("明文头", 0x0000, 0x1400), ("加扰区", 0x1400, 0x19800), ("TF100A", 0x19800, len(cont))]
f1 = scan("GT7868Q 容器 cont", cont, zones_cont)

zones_anch = [("头", 0, 0x1000), ("主体", 0x1000, len(anchor))]
f2 = scan("GT9896 anchor", anchor, zones_anch)

# ── 极端检验：找「整块 1024 逐字节完全相同」的位置 ──
print("=" * 88)
print("★ 整块 1024 逐字节完全相同的位置（K 泄露的强特征）")
print("=" * 88)
for name, d in (("cont", cont), ("anchor", anchor)):
    hits = []
    for off in range(0, len(d) - 2 * L):
        if d[off:off + L] == d[off + L:off + 2 * L]:
            hits.append(off)
    print("  %-8s 命中 %d 处" % (name, len(hits)))
    for h in hits[:12]:
        seg = d[h:h + L]
        print("     0x%05X  熵=%.4f  0x00=%.1f%% 0xFF=%.1f%%" % (
            h, ent(seg), 100 * seg.count(0) / L, 100 * seg.count(255) / L))
print()

# ── 3 KiB 以上连续高重复区（可能是长 0/FF 填充）──
print("=" * 88)
print("★ 长 0 / 长 FF 填充区（若在加扰区则明文基本是常量）")
print("=" * 88)
import re
for name, d in (("cont", cont), ("anchor", anchor)):
    for pat, lbl in ((b"\x00" * 64, "0x00"), (b"\xff" * 64, "0xFF")):
        ms = [m.start() for m in re.finditer(re.escape(pat), d)]
        if ms:
            print("  %-8s %s 连续 ≥64B 出现 %d 次，前几个位置: %s" % (
                name, lbl, len(ms), " ".join("0x%05X" % m for m in ms[:10])))
        else:
            print("  %-8s %s 无 ≥64B 连续" % (name, lbl))
