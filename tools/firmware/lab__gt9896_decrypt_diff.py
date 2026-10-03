"""解出 GT9896 明文，并与 GT7868Q 做 diff —— 找共享段 / 差异段。

GT9896 解码（与 GT7868Q 完全同构的写法）：
  纯区 anchor[0xD900:+1024]（1024 自相关 = 1.000000）
  Ma = anchor[0xD900:+1024]
  K'[j] = Ma[(j - 0xD900) % 1024]
  P[x] = anchor[x] ^ K'[x % 1024]
  理论相位校验：相对 Sa=0x1200 的相位 = (0x1200 - 0xD900) % 1024 = 256 ✓ 实测唯一尖峰
"""
import os
import collections

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
W = r"<WORKSPACE>"
anc = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
L = 1024

Ma = anc[0xD900:0xD900 + L]
Kp = bytes(Ma[(j - 0xD900) % L] for j in range(L))
KP = os.path.join(HERE, "GT9896_scramble_key.bin")
open(KP, "wb").write(Kp)

out = bytearray(anc)
for x in range(0x1000, len(anc)):
    out[x] = anc[x] ^ Kp[x % L]
PP = os.path.join(HERE, "GT9896_plain.bin")
open(PP, "wb").write(bytes(out))


def ent(b):
    if not b:
        return 0.0
    import math
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


print("产出：")
print("  K'      → %s (%d B)" % (KP, len(Kp)))
print("  明文     → %s (%d B)" % (PP, len(out)))
print()

print("=" * 94)
print("① GT9896 解密效果（与 GT7868Q 对照）")
print("=" * 94)
for name, rawseg, decseg in (
    ("GT7868Q 主体", open(os.path.join(W, "fw-touchpad", "touchpad_GT7868Q_fw.bin"), "rb").read()[0x1200:0x19800],
     d[0x1200:0x19800]),
    ("GT9896 主体", anc[0x1000:], bytes(out)[0x1000:]),
):
    print("  %-14s 0x00 %6.2f%% → %6.2f%%   熵 %.4f → %.4f" % (
        name, 100 * rawseg.count(0) / len(rawseg), 100 * decseg.count(0) / len(decseg),
        ent(rawseg), ent(decseg)))
print()

print("=" * 94)
print("② GT9896 明文的逐 4 KiB 熵剖面（判断内容性质）")
print("=" * 94)
p9 = bytes(out)
for i in range(0x1000, len(p9), 0x1000):
    seg = p9[i:i + 0x1000]
    if len(seg) < 512:
        break
    z = 100 * seg.count(0) / len(seg)
    tag = "全0" if z > 80 else ("空隙" if z > 12 else ("内容" if ent(seg) < 7.4 else "高熵"))
    print("  0x%05X  0x00=%6.2f%%  熵=%.4f  %s" % (i, z, ent(seg), tag))
print()

print("=" * 94)
print("③ 与 GT7868Q 明文做 diff：找公共片段")
print("=" * 94)
SEG = 16
g = d
P9 = p9
print("  长度：GT7868Q=%d  GT9896=%d" % (len(g), len(P9)))
# 同偏移相同率（分段）
STEP = 0x1000
same_by_zone = []
for s in range(0, min(len(g), len(P9)), STEP):
    e = min(s + STEP, len(g), len(P9))
    if e - s < 256:
        break
    eq = sum(1 for a, b in zip(g[s:e], P9[s:e]) if a == b) / (e - s)
    same_by_zone.append((eq, s))
print("  同偏移相同率最高的 10 个 4KiB 段：")
for eq, s in sorted(same_by_zone, reverse=True)[:10]:
    print("     0x%05X  相同率 %.4f (=%.2f/256)" % (s, eq, eq * 256))
print()
print("  同偏移相同率最低的 5 个：")
for eq, s in sorted(same_by_zone)[:5]:
    print("     0x%05X  相同率 %.4f" % (s, eq))
print()

# 公共长片段
aset = {}
for i in range(0, len(P9) - SEG):
    aset.setdefault(P9[i:i + SEG], i)
hits = {}
for j in range(0, len(g) - SEG):
    k = g[j:j + SEG]
    if k in aset:
        i = aset[k]
        m = 0
        while j + m < len(g) and i + m < len(P9) and g[j + m] == P9[i + m]:
            m += 1
        if m >= 24:
            hits.setdefault(m, (j, i))
print("  ≥24B 的公共片段（按长度，Top 12）：")
for m in sorted(hits, reverse=True)[:12]:
    j, i = hits[m]
    print("     长 %4d  GT7868Q[0x%05X] == GT9896[0x%05X]" % (m, j, i))
    print("           %s" % g[j:j + min(m, 40)].hex())
if not hits:
    print("     （无 ≥24B 公共片段）")
print()

print("=" * 94)
print("④ GT9896 明文里有没有代码特征 / 字符串")
print("=" * 94)
import re
b9 = p9[0x1000:]
print("  BL 高半字 %.1f/KB   32位指令 %.1f/KB" % (
    1000 * sum(1 for i in range(0, len(b9) - 3, 2) if 0xF0 <= b9[i + 1] <= 0xF7) / len(b9),
    1000 * sum(1 for i in range(0, len(b9) - 1, 2) if 0xE8 <= b9[i + 1] <= 0xFF) / len(b9)))
ss = re.findall(rb"[\x20-\x7e]{6,}", b9)
print("  ≥6 可打印串 %d 条" % len(ss))
for s in ss[:25]:
    print("     @0x%05X %s" % (0x1000 + b9.find(s), s.decode("latin-1")[:70]))
print()
print("  标识串搜索：")
for pat in (b"GT9896", b"9896", b"YELS", b"Goodix", b"Test", b"FW"):
    print("     %-10s %d 次" % (pat.decode(), b9.count(pat)))
