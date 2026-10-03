# -*- coding: utf-8 -*-
"""合并验证：
 ① 块0（= 官方 subsys[0] ISP）是不是 8051 代码？（向量表 / 操作码分布 / LJMP 目标）
 ② 16 字节周期是"定长记录表"还是"ECB 重复块"？逐列 mod16 熵说了算
 ③ L=16 是基频还是 1024 的谐波？
"""
import struct, collections, math

K = open("<WORKSPACE>", 'rb').read()
K316 = K[316:] + K[:316]
d = open("bios-re/GT7868Q_native_fw.bin", 'rb').read()


def parse(buf):
    for o in range(0, min(len(buf) - 300, 65536)):
        s = struct.unpack('>I', buf[o:o + 4])[0]
        if 1000 < s <= len(buf) - o and sum(buf[o + 6:o + 6 + s]) & 0xFFFF == \
                struct.unpack('>H', buf[o + 4:o + 6])[0]:
            ent = []
            for i in range(30):
                q = o + 0x20 + i * 8
                t = buf[q]
                ln = int.from_bytes(buf[q + 1:q + 5], 'big')
                if t == 0 and ln == 0:
                    break
                ent.append((t, ln))
            return o, ent
    return None


o, ent = parse(d)
off = o + 0x100
BL = []
for i, (t, ln) in enumerate(ent):
    xr = d[off:off + ln]
    off += ln
    BL.append((i, t, ln, bytes(v ^ K316[(k + 0x100) % 1024] for k, v in enumerate(xr))))

print("=" * 96)
print("① 块0（ISP，官方 subsys[0]）是不是 8051 代码？")
print("=" * 96)
b0 = BL[0][3]
print("  块0 size=%d  明文首 32 B: %s" % (len(b0), b0[:32].hex(' ')))
print("  8051 中断向量表判据：真 8051 程序在 0x00/0x03/0x0B/0x13/0x1B/0x23 处应为 02(LJMP) 或 12(LCALL)")
OFFS = [0x00, 0x03, 0x0B, 0x13, 0x1B, 0x23]
print("    实测该 6 个偏移的字节: %s  ⇒ %s"
      % (["%02x" % b0[x] for x in OFFS],
         "命中向量表" if sum(1 for x in OFFS if b0[x] in (0x02, 0x12)) >= 4 else "★不是 8051 向量表"))
OPS8051_MAIN = {0x02, 0x12, 0x22, 0x32, 0x74, 0x75, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F,
                0x90, 0xE4, 0xE5, 0xF0, 0xD2, 0xC2, 0xA3, 0x80, 0x70, 0x60, 0x50, 0x40, 0x20, 0x30,
                0xB4, 0xB5, 0x05, 0x15, 0x25, 0x35, 0x45, 0x85, 0xE0}
print("  8051 常见操作码密集度：")
for (i, t, ln, x) in BL:
    c = sum(1 for v in x if v in OPS8051_MAIN) / ln * 100
    print("    块%-2d t=0x%02x  %5.2f%%   0x02 出现率 %.3f%%  0x12 %.3f%%  (随机基线 0.39%%)"
          % (i, t, c, x.count(0x02) / ln * 100, x.count(0x12) / ln * 100))
print("  LJMP/LCALL 目标自洽性（02/12 后 2 字节组成的地址）：")
for (i, t, ln, x) in [BL[0]]:
    tg = []
    for j in range(ln - 2):
        if x[j] in (0x02, 0x12):
            tg.append((x[j + 1] << 8) | x[j + 2])
    if tg:
        print("    块0 共 %d 个 02/12；目标地址范围 0x%04X–0x%04X；落在本块内(0x%04X)的 %d 个"
              % (len(tg), min(tg), max(tg), ln, sum(1 for v in tg if v < ln)))
    else:
        print("    块0 无 02/12")

print()
print("=" * 96)
print("② 16 字节周期：是「定长记录表」还是「ECB 重复块」？")
print("=" * 96)
print("  判据 A：逐列 mod16 的各列熵（记录表 ⇒ 部分列远低于 8 bit）")
for (i, t, ln, x) in BL:
    if x.count(0) / ln > 0.6 or ln < 0x1000:
        continue
    cols = [x[j::16] for j in range(16)]
    ents = []
    for c in cols:
        cc = collections.Counter(c)
        ents.append(-sum(v / len(c) * math.log2(v / len(c)) for v in cc.values()))
    print("  块%-2d 各列熵: %s  最低列 H0=%.2f (%s)"
          % (i, " ".join("%.1f" % e for e in ents), min(ents), "有常量/低熵列" if min(ents) < 6 else "无低熵列"))
print()
print("  判据 B：是否存在重复的 16 字节块（ECB 特征）")
for (i, t, ln, x) in BL:
    if ln < 0x1000 or x.count(0) / ln > 0.9:
        continue
    nb = ln // 16
    c = collections.Counter(x[j * 16:(j + 1) * 16] for j in range(nb))
    dup = sum(v - 1 for v in c.values() if v > 1)
    print("  块%-2d 16B 块数=%-4d 不同=%-4d 重复块数=%d (%.2f%%)  %s"
          % (i, nb, len(c), dup, 100 * dup / nb, "有大量重复⇒ECB" if dup > nb * 0.05 else "无 ECB 特征"))
print()
print("  判据 C：L=16 是基频还是 1024 的谐波？（比较 16/32/48/64/1024 的匹配率）")
for (i, t, ln, x) in BL:
    if x.count(0) / ln > 0.6 or ln < 0x1000:
        continue
    r = {L: sum(1 for j in range(ln - L) if x[j] == x[j + L]) / (ln - L)
         for L in (16, 32, 48, 64, 128, 256, 512, 1024)}
    mono = all(r[16] >= r[32] * 0.9) and r[16] > r[1024] * 1.5
    print("  块%-2d L=16 %.4f | 32 %.4f | 48 %.4f | 64 %.4f | 128 %.4f | 256 %.4f | 512 %.4f | 1024 %.4f  %s"
          % (i, r[16], r[32], r[48], r[64], r[128], r[256], r[512], r[1024],
             "★16 是基频" if mono else "衰减平滑(非 16 基频)"))
