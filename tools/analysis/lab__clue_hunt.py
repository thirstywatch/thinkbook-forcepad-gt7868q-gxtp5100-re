"""线索搜索：在解出的 GT7868Q 明文固件里找「结构锚点」，为后续定位触觉代码铺路。"""
import os
import re
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
K = open(os.path.join(HERE, "GT7868Q_scramble_key.bin"), "rb").read()
seg = d[0x1200:0x19800]

print("=" * 84)
print("① 常见 32 位小端常量（地址/魔数）在明文中的出现")
print("=" * 84)
consts = {
    "0x08000000": 0x08000000, "0x20000000": 0x20000000,
    "0x40000000": 0x40000000, "0x00000000": 0x00000000,
    "0xFFFFFFFF": 0xFFFFFFFF, "0x0000FFFF": 0x0000FFFF,
    "0x00000100": 0x00000100, "0x00010000": 0x00010000,
    "0x12345678": 0x12345678, "0x5A5A5A5A": 0x5A5A5A5A,
}
for name, v in consts.items():
    p = v.to_bytes(4, "little")
    c = seg.count(p)
    pos = [m.start() + 0x1200 for m in re.finditer(re.escape(p), seg)]
    print("  %-12s 出现 %3d 次  前几个: %s" % (
        name, c, " ".join("0x%05X" % x for x in pos[:6])))
print()

print("=" * 84)
print("② 16 位小端常量")
print("=" * 84)
for v in (0x0000, 0xFFFF, 0x0100, 0x0080, 0x0001):
    p = v.to_bytes(2, "little")
    c = seg.count(p)
    print("  0x%04X  出现 %d 次 (%.2f%%)" % (v, c, 100 * c / (len(seg) // 2)))
print()

print("=" * 84)
print("③ K 自身是否也出现在明文头（未加扰区）")
print("=" * 84)
head = d[:0x1200]
print("  K 前 32B 在头中出现次数: %d" % head.count(K[:32]))
print("  K 中段 32B 在头中出现次数: %d" % head.count(K[480:512]))
# 反向：头里有没有 1024 周期的表
best = 0
for i in range(0, len(head) - 32):
    pass
print()

print("=" * 84)
print("④ 明文头部（0x0000-0x1200）的结构总览")
print("=" * 84)
for off in range(0, 0x1200, 0x100):
    s = d[off:off + 0x100]
    z = 100 * s.count(0) / len(s)
    ss = re.findall(rb"[\x20-\x7e]{4,}", s)
    print("  0x%05X  0x00=%5.1f%%  串: %s" % (
        off, z, " | ".join(x.decode("latin-1") for x in ss[:3])))
print()

print("=" * 84)
print("⑤ 头部关键点附近 dump")
print("=" * 84)
print("  0x1100-0x1200:")
print("   ", d[0x1100:0x1200].hex())
print("   ASCII:", "".join(chr(x) if 32 <= x < 127 else "." for x in d[0x1100:0x1200]))
print()
print("  0x1200-0x1280 (加扰区起点，已解密):")
print("   ", d[0x1200:0x1280].hex())
print()

print("=" * 84)
print("⑥ 明文里的「中文/UTF-8 多字节」与「长 ASCII」宽松搜索")
print("=" * 84)
ss = re.findall(rb"[\x20-\x7e]{8,}", bytearray(d))
print("  ≥8 可打印串共 %d 条" % len(ss))
seen = set()
for s in ss[:40]:
    t = s.decode("latin-1")
    if t not in seen:
        seen.add(t)
        print("     ", t)
