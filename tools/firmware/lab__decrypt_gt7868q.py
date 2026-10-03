"""GT7868Q 加扰区解密（K 已确认）：输出明文 + 结构分析 + GT9896 交叉验证。

K 定义：K[j] = Mc[(j - 240) % 1024]，Mc = cont[0x084F0:0x084F0+1024]
解码：P[x] = C[x] ^ K[x % 1024]
  ⇒ 相对任意起点 S 的相位 = (S - 240) % 1024；S=0x1200 时 = 272
证据：纯区(明文全0) P[x]=C[x]^Mc[(x-240)%1024]=C[x]^C[x]=0 ✓ 数学自洽
      相位扫描 272 处 0x00 数 7455 vs 次优 534（14倍）✓ 实测唯一尖峰
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
Mc = cont[0x084F0:0x084F0 + L]
PHASE_BASE = 240          # K[j] = Mc[(j-240)%1024]


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


def key(x):
    return Mc[(x - PHASE_BASE) % L]


def decrypt(d, s, e):
    return bytes(d[x] ^ key(x) for x in range(s, e))


# ── ① 全量解密 cont ──
out = bytearray(cont)
S0 = 0x1200
plain_part = decrypt(cont, S0, len(cont))
out[S0:] = plain_part
OUT = os.path.join(HERE, "GT7868Q_plain.bin")
open(OUT, "wb").write(bytes(out))
print("已写出明文 → %s（%d B）" % (OUT, len(out)))
print()

print("=" * 92)
print("① 解密效果总览")
print("=" * 92)
print("  加扰区 cont[0x%05X:0x%05X]  %d B" % (S0, len(cont), len(cont) - S0))
print("  0x00 比例  %.4f%% → %.4f%%" % (
    100 * cont[S0:].count(0) / len(cont[S0:]), 100 * plain_part.count(0) / len(plain_part)))
print("  熵        %.4f → %.4f" % (ent(cont[S0:]), ent(plain_part)))
print()

print("=" * 92)
print("② 逐 1 KiB 结构剖面（0x00 比例 / 熵）—— 判断是否还有第二层")
print("=" * 92)
print("  %-10s %-10s %-10s %s" % ("偏移", "0x00%", "熵", "判定"))
for i in range(0, len(plain_part), L):
    seg = plain_part[i:i + L]
    if len(seg) < 256:
        break
    z = 100 * seg.count(0) / len(seg)
    e = ent(seg)
    tag = "全0填充" if z > 80 else ("部分空隙" if z > 10 else ("代码?" if e < 7.3 else "高熵"))
    print("  0x%05X   %-10.2f %-10.4f %s" % (S0 + i, z, e, tag))
print()

print("=" * 92)
print("③ 可打印字符串搜索（明文全文件）")
print("=" * 92)
ss = re.findall(rb"[\x20-\x7e]{6,}", bytes(out))
print("  共 %d 条" % len(ss))
for s in ss[:60]:
    print("   @0x%05X  %s" % (bytes(out).find(s), s.decode("latin-1")[:76]))
print()

print("=" * 92)
print("④ 交叉验证：GT9896 用自己的完整相位搜索（K 是否通用？）")
print("=" * 92)
Sa = 0x1200
probe = anchor[Sa:Sa + 0x8000]
rows = []
for ph in range(L):
    p = bytes(probe[i] ^ Mc[(i + ph) % L] for i in range(len(probe)))
    z = p.count(0)
    mz = 0; cur = 0
    for x in p:
        cur = cur + 1 if x == 0 else 0
        mz = max(mz, cur)
    rows.append((z, mz, ent(p), ph))
rows.sort(reverse=True)
print("  基线 0x00 期望 = %d" % (len(probe) // 256))
for z, mz, e, ph in rows[:8]:
    print("     0x00=%-7d 最长0段=%-6d 熵=%.4f ph=%d" % (z, mz, e, ph))
print()

print("=" * 92)
print("⑤ 明文头部（0x0000-0x1200，原本就未加扰）")
print("=" * 92)
head = bytes(out)[:0x1200]
print("  熵=%.4f  0x00=%.2f%%" % (ent(head), 100 * head.count(0) / len(head)))
ss2 = re.findall(rb"[\x20-\x7e]{5,}", head)
print("  字符串 %d 条：" % len(ss2))
for s in ss2[:30]:
    print("     @0x%05X %s" % (head.find(s), s.decode("latin-1")[:70]))
