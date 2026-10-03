# -*- coding: utf-8 -*-
"""修正记录边界为 0x4C（= 文件前导 76 B 之后），每条 1084 B = 1024 B 配置体 + 60 B 尾"""
import struct, collections, math
d = open("bios-re/GT7868Q_native_fw.bin", 'rb').read()
PRO = d[0:0x4C]
BASE = 0x4C; STRIDE = 0x43C
R = [d[BASE + k * STRIDE: BASE + (k + 1) * STRIDE] for k in range(4)]
print("=== 0. 文件前导 76 B (0x00-0x4B) ===")
print(" ", PRO.hex(' '))
print("  BE u32 每 4 B:", [hex(int.from_bytes(PRO[i:i+4],'big')) for i in range(0,76,4)])
print()
print("=== 1. 4 条记录（各 1084 B = 1024 体 + 60 尾）差异 ===")
for k in range(4):
    body = R[k][:1024]; tail = R[k][1024:]
    print("  记录%d @0x%X  body[0:16]=%s  tail[0:16]=%s" % (k, BASE+k*STRIDE, body[:16].hex(' '), tail[:16].hex(' ')))
for k in range(1, 4):
    db = [j for j in range(1024) if R[k][j] != R[0][j]]
    dt = [j for j in range(1024, 1084) if R[k][j] != R[0][j]]
    print("  记录%d vs 记录0: 体差异 %d B, 尾差异 %d B" % (k, len(db), len(dt)))
    if db[:1]:
        print("     体差异偏移（前20）:", [hex(x) for x in db[:20]])
        for j in db[:8]:
            print("       +0x%03X 0x%-4s->0x%-4s" % (j, "%02x" % R[0][j], "%02x" % R[k][j]))
print("  记录1 vs 2 vs 3 体差异:", sum(1 for j in range(1024) if R[1][j]!=R[2][j]),
      sum(1 for j in range(1024) if R[1][j]!=R[3][j]))
print()
print("=== 2. 记录1 的 60 B 尾部 ===")
T = R[1][1024:]
print("  hex:", T.hex(' '))
print("  BE u16:", list(struct.unpack('>30H', T)))
print("  LE u16:", list(struct.unpack('<30H', T)))
print("  记录0 尾全 0 ?", all(x == 0 for x in R[0][1024:]))
print()
print("=== 3. 活体 0x96F8 与各记录的关系 ===")
live = bytes.fromhex("22011B003E010465A7C3E102B5021F1471489320")
for k in range(4):
    h = [i for i in range(1084-20) if R[k][i:i+20] == live]
    print("  记录%d: %s" % (k, [hex(x) for x in h] or "无"))
print("  ⇒ 若 4 条都在 +0x00，则【每条记录本身就是配置体】，1084 = 1024 体 + 60 尾")
print()
print("=== 4. 配置体（记录1 前 1024 B）逐 64 B 段落概览 ===")
B = R[1][:1024]
for i in range(0, 1024, 64):
    seg = B[i:i+64]
    c = collections.Counter(seg)
    print("  +0x%03X H0=%.2f  top=%s  | %s" % (i,
        -sum(v/64*math.log2(v/64) for v in c.values()),
        ",".join("%02x×%d" % (v, n) for v, n in c.most_common(3)),
        seg[:24].hex(' ')))
print()
print("=== 5. 尾 60 B：4 条是否相同？是否与体重复？===")
for k in range(4):
    print("  记录%d 尾: %s" % (k, R[k][1024:1040].hex(' ')))
t1 = R[1][1024:]
print("  尾 60 B 是否出现在记录1 的体内:",
      [hex(i) for i in range(1024-60) if R[1][i:i+60] == t1] or "否")
print("  4 条尾部两两相同:", [sum(1 for a,b in zip(R[1][1024:], R[k][1024:]) if a==b) for k in range(4)])
