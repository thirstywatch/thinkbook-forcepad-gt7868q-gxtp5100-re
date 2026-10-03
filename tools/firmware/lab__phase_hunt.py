"""相位精定：正确 K 的正确相位应让解码结果出现「固件特征」——
   大量 0x00 填充（未使用区）、长连续 0 段。
   判据优于熵：固件代码熵未必低，但空隙一定是 0。

同时对 Mc 的身份做交叉判定：
   - 若 Mc 是 K：解码后 0x00 比例应显著 > 1/256
   - 若 Mc 只是明文表：解码后仍均匀
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


def maxzero(b):
    best = cur = 0
    for x in b:
        cur = cur + 1 if x == 0 else 0
        if cur > best:
            best = cur
    return best


Mc = cont[0x084F0:0x084F0 + L]
Ma = anchor[0x0D900:0x0D900 + L]

S, E = 0x1200, 0x19800
seg = cont[S:E]
N = len(seg)
print("待解段 cont[0x%05X:0x%05X] = %d B" % (S, E, N))
print("原始密文：0x00 比例 %.4f%%  熵 %.4f  最长连续 0 段 %d" % (
    100 * seg.count(0) / N, ent(seg), maxzero(seg)))
print()

print("=" * 92)
print("① 用 Mc 按 1024 相位解扰，找「0x00 填充」最多的相位")
print("=" * 92)
probe = seg[:0x8000]
rows = []
for ph in range(L):
    p = bytes(probe[i] ^ Mc[(i + ph) % L] for i in range(len(probe)))
    rows.append((p.count(0), maxzero(p), ent(p), ph))
rows.sort(reverse=True)
print("  %-10s %-12s %-10s %s" % ("0x00个数", "最长0段", "熵", "相位"))
for z, mz, e, ph in rows[:10]:
    print("  %-10d %-12d %-10.4f ph=%d" % (z, mz, e, ph))
print()
tot = len(probe)
print("  基线：随机数据 0x00 期望 = %d 个 (%.3f%%)" % (tot // 256, 100 / 256))
print()

print("=" * 92)
print("② 用 Ma 同样搜（验证两者等价）")
print("=" * 92)
rows2 = []
for ph in range(L):
    p = bytes(probe[i] ^ Ma[(i + ph) % L] for i in range(len(probe)))
    rows2.append((p.count(0), maxzero(p), ent(p), ph))
rows2.sort(reverse=True)
for z, mz, e, ph in rows2[:5]:
    print("  %-10d %-12d %-10.4f ph=%d" % (z, mz, e, ph))
print()

# ── ③ 用最优相位解全段，dump 结构 ──
best_ph = rows[0][3]
print("=" * 92)
print("③ 用 ph=%d 解全加扰区，dump 结构" % best_ph)
print("=" * 92)
plain = bytes(seg[i] ^ Mc[(i + best_ph) % L] for i in range(N))
print("  0x00 比例 %.4f%%（原 %.4f%%）  熵 %.4f（原 %.4f）  最长0段 %d" % (
    100 * plain.count(0) / N, 100 * seg.count(0) / N, ent(plain), ent(seg), maxzero(plain)))
print()
print("  前 256B:")
print("    ", plain[:256].hex())
print("  ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in plain[:256]))
print()

# 找长 0 段位置
print("  连续 ≥32B 的 0 段位置：")
runs = []
cur = None
for i, x in enumerate(plain):
    if x == 0:
        if cur is None:
            cur = i
    else:
        if cur is not None and i - cur >= 32:
            runs.append((S + cur, i - cur))
        cur = None
print("   ", [(hex(a), b) for a, b in runs[:20]], "共 %d 段" % len(runs))
print()

# ④ 用同一相位解码 anchor 的对应段，做交叉验证
print("=" * 92)
print("④ 交叉验证：用同一 K 解 GT9896")
print("=" * 92)
Sa, Ea = 0x1200, len(anchor)
sega = anchor[Sa:Ea]
plaina = bytes(sega[i] ^ Mc[(i + best_ph) % L] for i in range(len(sega)))
print("  GT9896 0x00 比例 %.4f%%（原 %.4f%%）  熵 %.4f（原 %.4f）" % (
    100 * plaina.count(0) / len(sega), 100 * sega.count(0) / len(sega),
    ent(plaina), ent(sega)))
print("  前 128B:", plaina[:128].hex())
