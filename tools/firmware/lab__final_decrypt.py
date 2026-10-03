"""★★★★★★★ 收网：用提取出的 K 全量解开 GT7868Q 加扰区，验证是否得到真明文。

已确证：
  Mc(cont 0x084F0+, 1024B) == rotate(Ma(anchor 0x0D900+, 1024B), 692)
  Mc：熵 8.0，256 个字节值各有 4 次 ⇒ 构造表（很可能是 K 或其循环移位）
  用 Mc 解扰 cont[0x1400+]：熵 7.9865 → 6.5169（显著下降）

本脚本：
  1. 周期检验（K 是 1024 周期还是 256 周期）
  2. 相位搜索（判据 = 明文熵最低 + 可打印/字符串最多）
  3. 全量解扰 cont，搜 ASCII 字符串
  4. 逐 4 KiB 熵剖面（看解出明文的真实结构）
  5. 交叉验证：同一 K 解 anchor
"""
import os
import collections
import math
import re

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


Mc = cont[0x084F0:0x084F0 + L]

print("=" * 90)
print("① K 的周期检验")
print("=" * 90)
print("  Mc[0:256]  == Mc[256:512]  ? %s" % (Mc[0:256] == Mc[256:512]))
print("  Mc[0:512]  == Mc[512:1024] ? %s" % (Mc[0:512] == Mc[512:1024]))
print("  Mc[0:128]  == Mc[128:256]  ? %s" % (Mc[0:128] == Mc[128:256]))
print()

print("=" * 90)
print("② 相位搜索（在 cont[0x1400:0x1400+16384] 上；判据=熵最低）")
print("=" * 90)
S = 0x1400
probe = cont[S:S + 0x4000]
res = []
for ph in range(L):
    p = bytes(probe[i] ^ Mc[(i + ph) % L] for i in range(len(probe)))
    res.append((ent(p), ph))
res.sort()
print("  最佳 8 个相位：")
for ev, ph in res[:8]:
    print("     ph=%4d  明文熵=%.4f" % (ph, ev))
print("  最差：ph=%d 熵=%.4f" % (res[-1][1], res[-1][0]))
best_ph = res[0][1]
print()

print("=" * 90)
print("③ 用最佳相位解 cont 全加扰区")
print("=" * 90)
S, E = 0x1200, 0x19800
seg = cont[S:E]
plain = bytes(seg[i] ^ Mc[(i + best_ph) % L] for i in range(len(seg)))
print("  解出 %d B，熵=%.4f" % (len(plain), ent(plain)))
print("  前 128B HEX:", plain[:128].hex())
print("  ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in plain[:128]))
print()

ss = re.findall(rb"[\x20-\x7e]{6,}", plain)
print("  可打印串（≥6）共 %d 条，前 30：" % len(ss))
for s in ss[:30]:
    print("     ", s.decode("latin-1")[:78])
print()

print("=" * 90)
print("④ 逐 4 KiB 熵剖面（解出明文）")
print("=" * 90)
for i in range(0, len(plain), 0x1000):
    seg2 = plain[i:i + 0x1000]
    if len(seg2) < 512:
        break
    e = ent(seg2)
    bar = "#" * int(max(0, (e - 4.0)) * 8)
    print("  0x%05X  熵=%.4f  %s" % (S + i, e, bar))
print()

# ── ⑤ 交叉验证：同一 K 解 GT9896 ──
print("=" * 90)
print("⑤ 交叉验证：用同一 K 解 GT9896（判据：应同样得到低熵明文）")
print("=" * 90)
for ph in range(L):
    p = anchor[0x1000:0x5000]
    pp = bytes(p[i] ^ Mc[(i + ph) % L] for i in range(len(p)))
    if ph == 0 or ent(pp) < best2[0]:
        best2 = (ent(pp), ph, pp)
print("  GT9896 最佳相位 %d  明文熵=%.4f （原熵 %.4f）" % (
    best2[1], best2[0], ent(anchor[0x1000:0x5000])))
ss2 = re.findall(rb"[\x20-\x7e]{6,}", best2[2])
print("  可打印串 %d 条，前 10：" % len(ss2))
for s in ss2[:10]:
    print("     ", s.decode("latin-1")[:78])
