"""容器结构快检：段划分 / 熵 / ASCII / 字节分布 / 首尾十六进制。
目的：判断 0x1400-0x19A00 那段到底是【加扰】【压缩】还是【明文但非代码】。"""

import os, math, collections, re

D = r"<WORKSPACE>"
data = open(os.path.join(D, "touchpad_GT7868Q_fw.bin"), "rb").read()
print("容器大小 =", len(data), "= 0x%X" % len(data))

def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

print("\n=== 每 4 KiB 的熵（7.9+ 基本等于随机；<7 有结构）===")
for off in range(0, len(data), 0x1000):
    seg = data[off:off + 0x1000]
    e = ent(seg)
    bar = "#" * int((e - 5) * 12) if e > 5 else ""
    print("  0x%06X  %.3f  %s" % (off, e, bar))

print("\n=== 首 256 字节 ===")
for i in range(0, 256, 16):
    row = data[i:i + 16]
    print("  0x%04X  %-47s  %s" % (i, " ".join("%02X" % x for x in row),
                                   "".join(chr(x) if 32 <= x < 127 else "." for x in row)))

print("\n=== 0x1400 起 256 字节（加扰区开头）===")
for i in range(0x1400, 0x1400 + 256, 16):
    row = data[i:i + 16]
    print("  0x%04X  %-47s  %s" % (i, " ".join("%02X" % x for x in row),
                                   "".join(chr(x) if 32 <= x < 127 else "." for x in row)))

print("\n=== 0x19A00 起 128 字节（TF100A 明文起点）===")
for i in range(0x19A00, 0x19A00 + 128, 16):
    row = data[i:i + 16]
    print("  0x%04X  %-47s  %s" % (i, " ".join("%02X" % x for x in row),
                                   "".join(chr(x) if 32 <= x < 127 else "." for x in row)))

print("\n=== 全容器 ASCII 串（>=8，取样前 40 条）===")
strs = [(m.start(), m.group()) for m in re.finditer(rb"[\x20-\x7e]{8,}", data)]
print("  共 %d 条" % len(strs))
for off, s in strs[:40]:
    print("   0x%06X  %s" % (off, s.decode('latin-1')[:70]))

seg = data[0x1400:0x19A00]
print("\n=== 加扰段（0x1400-0x19A00，%d 字节）字节直方图 Top20 ===" % len(seg))
for b, n in collections.Counter(seg).most_common(20):
    print("   %02X  %6d  %.3f%%" % (b, n, 100.0 * n / len(seg)))
print("  段内熵 = %.4f" % ent(seg))
print("  段内 0x00 占比 %.4f%%   0xFF 占比 %.4f%%" % (
    100.0 * seg.count(0) / len(seg), 100.0 * seg.count(0xFF) / len(seg)))
