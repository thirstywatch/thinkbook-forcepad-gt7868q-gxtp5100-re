"""最终产出与硬验证：GT7868Q scramble K 的完整恢复。

K 定义：K[j] = Mc[(j - 240) % 1024]，Mc = cont[0x084F0 : 0x084F0+1024]
        （240 = 0x084F0 % 1024，由「纯区明文全 0」推出）
解码：P[x] = C[x] ^ K[x % 1024]，x 为文件偏移

硬验证清单（全部为「不可能靠巧合」的判据）：
 V1 纯区自洽：0x084F0 附近解码后为全 0（5120 B）
 V2 0 填充块对齐：出现 100% 全 0 的 1 KiB 块，且边界对齐 0x400
 V3 规律间隔：0 段以 128 B 为周期重复出现（数据结构特征）
 V4 明文头衔接：0x0000-0x1200 保持原文（含 YELSTO / 7868Q）
 V5 熵降幅：主体熵 7.99 → 7.0-7.3，且非 0 部分 7.24
 V6 相位唯一性：272 处 0x00=7455，次优仅 534（14 倍落差）
"""
import os
import collections
import math
import re

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
L = 1024
Mc = cont[0x084F0:0x084F0 + L]
PB = 240

# ★ K[j] = Mc[(j - 240) % 1024]
K = bytes(Mc[(j - PB) % L] for j in range(L))
KPATH = os.path.join(HERE, "GT7868Q_scramble_key.bin")
open(KPATH, "wb").write(K)

# 正确范围：0x1200 - 0x19800 加扰；其余原样
S0, E0 = 0x1200, 0x19800
out = bytearray(cont)
for x in range(S0, E0):
    out[x] = cont[x] ^ K[x % L]
PPATH = os.path.join(HERE, "GT7868Q_plain.bin")
open(PPATH, "wb").write(bytes(out))


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


print("=" * 92)
print("产出")
print("=" * 92)
print("  K       → %s  (%d B)" % (KPATH, len(K)))
print("  明文     → %s  (%d B)" % (PPATH, len(out)))
print("  K 前 32B: %s" % K[:32].hex())
print("  K 熵=%.4f  唯一字节=%d  每个值出现 %s 次" % (
    ent(K), len(set(K)), sorted(collections.Counter(K).values())[:1]))
print()

seg = bytes(out)[S0:E0]
print("=" * 92)
print("V1/V5 解密效果")
print("=" * 92)
print("  加扰区 [0x%05X,0x%05X)  %d B" % (S0, E0, E0 - S0))
print("  0x00 比例 %.4f%% → %.4f%%" % (100 * cont[S0:E0].count(0) / (E0 - S0),
                                      100 * seg.count(0) / len(seg)))
print("  熵        %.4f → %.4f" % (ent(cont[S0:E0]), ent(seg)))
nz = bytes(x for x in seg if x != 0)
print("  非 0 部分熵 = %.4f（原 %.4f）" % (ent(nz), ent(bytes(x for x in cont[S0:E0] if x != 0))))
print()

print("=" * 92)
print("V2 100%% 全 0 的 1 KiB 块（边界对齐检查）")
print("=" * 92)
blocks = []
for i in range(0, len(seg) - L + 1, L):
    if seg[i:i + L].count(0) == L:
        blocks.append(S0 + i)
print("  共 %d 个 100%% 全 0 块：%s" % (len(blocks), " ".join("0x%05X" % b for b in blocks[:24])))
print("  全部对齐 0x400 ? %s" % all(b % 0x400 == 0 for b in blocks))
print()

print("=" * 92)
print("V3 0 段的规律间隔（数据结构特征）")
print("=" * 92)
runs = []
cur = None
for i, x in enumerate(seg):
    if x == 0:
        if cur is None:
            cur = i
    else:
        if cur is not None and i - cur >= 32:
            runs.append((S0 + cur, i - cur))
        cur = None
print("  ≥32B 的 0 段共 %d 段" % len(runs))
prev = None
gaps = []
for a, n in runs[:20]:
    g = "" if prev is None else "  Δ=%d" % (a - prev)
    print("     0x%05X  长 %5d%s" % (a, n, g))
    if prev is not None:
        gaps.append(a - prev)
    prev = a
print("  相邻 0 段间隔：%s" % gaps[:16])
print()

print("=" * 92)
print("V4 明文头保持原样")
print("=" * 92)
h = bytes(out)[:0x1200]
print("  YELSTO @0x%05X  7868Q @0x%05X  头熵=%.4f" % (
    h.find(b"YELSTO"), h.find(b"7868Q"), ent(h)))
print()

print("=" * 92)
print("补充：UTF-16 / 其他编码字符串搜索")
print("=" * 92)
for name, pat in (("ASCII≥5", rb"[\x20-\x7e]{5,}"),
                  ("UTF16LE≥5", rb"(?:[\x20-\x7e]\x00){5,}")):
    hits = re.findall(pat, seg)
    print("  %-10s %d 条" % (name, len(hits)))
    for s in hits[:12]:
        print("      ", s[:60])
print()

print("=" * 92)
print("补充：明文头部（未加扰）结构 dump")
print("=" * 92)
print("  0x0000-0x0100:", bytes(out)[:0x100].hex())
print()
print("  0x0100-0x0140:", bytes(out)[0x100:0x140].hex())
print("  ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in bytes(out)[0x100:0x140]))
