# -*- coding: utf-8 -*-
import struct, collections
d = open("bios-re/GT7868Q_native_fw.bin", 'rb').read()
R = [d[0x10 + i * 0x43C: 0x10 + (i + 1) * 0x43C] for i in range(4)]
H = R[1][:0x3C]; B = R[1][0x3C:0x43C]
print("=== A. 60 B 头部（记录1，全 4 条本体相同；记录0 该区全 0）===")
print("  hex:", H.hex(' '))
print("  LE u16:", [hex(x) for x in struct.unpack('<30H', H)])
print("  BE u16:", [hex(x) for x in struct.unpack('>30H', H)])
print("  LE u16 十进制:", list(struct.unpack('<30H', H)))
print("  BE u16 十进制:", list(struct.unpack('>30H', H)))
print("  字节直方: distinct=%d  ff×%d  00×%d" % (len(set(H)), H.count(0xff), H.count(0)))

print()
print("=== B. 1024 B 配置体：结构概览（跑长/平台）===")
seg = []
i = 0
while i < 1024:
    v = B[i]; j = i
    while j < 1024 and B[j] == v: j += 1
    if j - i >= 6:
        seg.append((i, j - i, v))
    i = j
print("  长度≥6 的常量平台共 %d 段（占 %d B / 1024 = %.0f%%）："
      % (len(seg), sum(l for _, l, _ in seg), sum(l for _, l, _ in seg) / 1024 * 100))
for o, l, v in seg:
    print("    +0x%03X 长 %3d 值 0x%02X (%d)" % (o, l, v, v))

print()
print("=== C. 关键阈值搜索（体 + 头 + 全记录）===")
targets = [140, 98, 70, 48, 20, 100, 112, 116, 104, 90, 80, 120, 166, 177, 60, 50]
for name, buf in [("记录1 全 1084B", R[1]), ("配置体 1024B", B)]:
    le = list(struct.unpack('<%dH' % (len(buf) // 2), buf[:len(buf) // 2 * 2]))
    ble = list(struct.unpack('>%dH' % (len(buf) // 2), buf[:len(buf) // 2 * 2]))
    cl, cb = collections.Counter(le), collections.Counter(ble)
    bl = collections.Counter(buf)
    print("  --- %s ---" % name)
    print("    %-6s %s" % ("值", "  ".join("%d" % t for t in targets)))
    print("    %-6s %s" % ("LE16", "  ".join("%d" % cl[t] for t in targets)))
    print("    %-6s %s" % ("BE16", "  ".join("%d" % cb[t] for t in targets)))
    print("    %-6s %s" % ("u8", "  ".join("%d" % bl[t] for t in targets)))

print()
print("=== D. 活体读回的两个地址 是否在记录中出现 ===")
live96f8 = bytes.fromhex("22011B003E010465A7C3E102B5021F1471489320")
live19000 = bytes.fromhex("FFFAFFFDFFFD000100000000FFFEFFFF000000000000FFFF0001")
for nm, pat in [("0x96F8 首20B", live96f8), ("0x19000 首16B", live19000)]:
    hits = [i for i in range(len(R[1]) - len(pat) + 1) if R[1][i:i + len(pat)] == pat]
    print("  %-14s 在记录中的位置: %s" % (nm, [hex(h) for h in hits] or "无"))
    for r in range(1, 4):
        h2 = [i for i in range(len(R[r]) - len(pat) + 1) if R[r][i:i + len(pat)] == pat]
        print("       记录%d: %s" % (r, [hex(x) for x in h2] or "无"))

print()
print("=== E. 1024 B 体的字节直方与熵 ===")
import math
c = collections.Counter(B)
H0 = -sum(v / len(B) * math.log2(v / len(B)) for v in c.values())
print("  不同值 %d/256  H0=%.4f  ff×%d(%.1f%%)  00×%d(%.1f%%)"
      % (len(c), H0, B.count(0xff), B.count(0xff) / 10.24, B.count(0), B.count(0) / 10.24))
print("  最高频值 top10:", c.most_common(10))
print("  0xFF/0x00 之外的值域: min=%d max=%d" % (min(v for v in c if v not in (0, 0xff)),
                                                 max(v for v in c if v not in (0, 0xff))))

print()
print("=== F. 记录 0 vs 记录 1：全 1084 B 差异明细 ===")
diff = [j for j in range(1084) if R[0][j] != R[1][j]]
print("  差异字节数 =", len(diff), " 全部落在 0x%03X..0x%03X" % (diff[0], diff[-1]))
print("  记录0 该区全 0 ?", all(R[0][j] == 0 for j in diff))
print("  ⇒ 结论：记录 0 = 【头部清零】的同一份配置；记录 1/2/3 = 带头部的同一份配置")
