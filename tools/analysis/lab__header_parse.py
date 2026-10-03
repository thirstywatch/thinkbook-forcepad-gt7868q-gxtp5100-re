"""明文头结构解析（0x0000-0x1200，未加扰区）—— 找触觉/配置字段。

已知：4 个 0x43C 字节的完全相同的块（0x40000000 出现在每块的 +0x3F0 处）。
头部是唯一「未加扰、可直接读」的区域 ⇒ 配置类参数（含可能的触觉参数）最可能在这里。
"""
import os
import collections
import struct

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
raw = open(r"<WORKSPACE>", "rb").read()
anc = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()

print("=" * 94)
print("① 头部块结构确认")
print("=" * 94)
BLK = 0x43C
blocks = [d[i * BLK:(i + 1) * BLK] for i in range(4)]
print("  4 个块是否完全相同: %s" % all(b == blocks[0] for b in blocks))
print("  块 0 前 64B: %s" % blocks[0][:64].hex())
print("  块 0 后 64B: %s" % blocks[0][-64:].hex())
print()
print("  0x0000-0x0100（块外/头前部）: %s" % d[:0x100].hex())
print("  0x10F0-0x1200（元数据区）  : %s" % d[0x10F0:0x1200].hex())
print()

print("=" * 94)
print("② 块 0 的 32 位小端字段扫描（含 0x40000000 的上下文）")
print("=" * 94)
b = blocks[0]
off = b.find((0x40000000).to_bytes(4, "little"))
while off >= 0:
    lo = max(0, off - 32)
    print("  +0x%03X 字段区:" % off)
    for j in range(0, 64, 4):
        v = struct.unpack_from("<I", b, off - 32 + j)[0] if off - 32 + j + 4 <= len(b) else None
        if v is not None:
            print("      +0x%03X : %08X" % (off - 32 + j, v))
    break
print()

print("=" * 94)
print("③ 头部里「重复出现的 16 位值」—— 表项特征")
print("=" * 94)
h = d[:0x1200]
c16 = collections.Counter(h[i] | (h[i + 1] << 8) for i in range(0, len(h) - 1, 2))
print("  最常见 16 位值 Top 20：")
for v, n in c16.most_common(20):
    print("     0x%04X  ×%d" % (v, n))
print()

print("=" * 94)
print("④ 头部 0x43C 块的「差异图」—— 块内哪些位置在 4 块之间不同（若有）")
print("=" * 94)
diff = [i for i in range(BLK) if len({blocks[k][i] for k in range(4)}) > 1]
print("  4 块之间不同的字节数：%d / %d" % (len(diff), BLK))
print("  前 40 个差异位置：%s" % diff[:40])
print()

print("=" * 94)
print("⑤ 与 GT9896 头部逐字节对齐比较（前 0x1200）")
print("=" * 94)
n = min(0x1200, len(anc))
eq = sum(1 for i in range(n) if d[i] == anc[i]) / n
print("  GT7868Q[0:0x1200] vs GT9896[0:0x1200] 相同率 %.4f (=%.2f/256)" % (eq, eq * 256))
print()
print("  GT9896 头前 128B: %s" % anc[:128].hex())
print("  GT7868Q头前 128B: %s" % d[:128].hex())
print()
# 找公共子串
SEG = 12
aset = {}
for i in range(len(anc) - SEG):
    aset.setdefault(anc[i:i + SEG], i)
found = {}
for j in range(0x1200 - SEG):
    k = d[j:j + SEG]
    if k in aset:
        i = aset[k]
        m = 0
        while j + m < 0x1200 and i + m < len(anc) and d[j + m] == anc[i + m]:
            m += 1
        found.setdefault(m, (j, i))
print("  ≥12B 公共串（Top 10，按长度）:")
for m in sorted(found, reverse=True)[:10]:
    j, i = found[m]
    print("     长 %3d  GT7868Q[0x%05X] == GT9896[0x%05X]" % (m, j, i))
    print("           %s" % d[j:j + min(m, 40)].hex())
print()

print("=" * 94)
print("⑥ 头部是否含触觉线索（字节级）")
print("=" * 94)
for val, desc in [(0x5A, "AW86927 地址A"), (0x5B, "地址B"), (0xB4, "写地址"), (0xB5, "读地址"),
                  (0xB6, "写地址2"), (0xB7, "读地址2"), (0xCA, "CA4F 高"), (0x4F, "CA4F 低")]:
    print("  0x%02X (%s) 在头部出现 %d 次" % (val, desc, h.count(val)))
print()
print("  头部里 32 位小端常量:")
for v in (0x5A, 0x5B, 0xB4, 0xB6, 0xCA4F, 0x40000000, 0x20000000, 0x08000000):
    p = v.to_bytes(4, "little")
    print("     %#010x : %d 次" % (v, h.count(p)))
