# -*- coding: utf-8 -*-
"""严格版：明文里有没有 AW86927 / I²C 主机痕迹 + 这些数据到底是什么
纪律：任何"频次异常"必须与【等长真随机】对照；4 字节常量必须用 4 字节扫描。
"""
import struct, collections, math, os, re

KWIN = "<WORKSPACE>"
K = open(KWIN, 'rb').read()
K316 = K[316:] + K[:316]
SRC = {
    "本机2024": "bios-re/GT7868Q_native_fw.bin",
    "2020": "poc/goodix-fw/goodix_tp_payload.bin",
    "GT9896": "poc/anchor-hunt/goodix_gt9896_fw.bin",
    "GT7863": "<WORKSPACE>",
}


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


def blocks(path):
    b = open(path, 'rb').read()
    o, ent = parse(b)
    off = o + 0x100
    out = []
    for i, (t, ln) in enumerate(ent):
        xr = b[off:off + ln]
        off += ln
        out.append((i, t, ln, bytes(v ^ K316[(k + 0x100) % 1024] for k, v in enumerate(xr)), xr))
    return out


ALL = {}
for nm, p in SRC.items():
    ALL[nm] = blocks(p)

print("=" * 100)
print("【1】AW86927 / I²C 主机常量 —— 严格对照（4 字节模式；随机基线 = 等长 os.urandom×20 次平均）")
print("=" * 100)
PATS = {
    "0x5A 单字节": [b'\x5a'],
    "0x9270 BE": [b'\x92\x70'],
    "0x9270 LE": [b'\x70\x92'],
    "I2C CR1_START 0x00000100": [struct.pack('<I', 0x100)],
    "I2C CR1_STOP  0x00000200": [struct.pack('<I', 0x200)],
    "I2C CR1_ACK   0x00000400": [struct.pack('<I', 0x400)],
    "I2C CR1_SWRST 0x00008000": [struct.pack('<I', 0x8000)],
    "I2C1 base 0x40005400": [struct.pack('<I', 0x40005400)],
    "I2C2 base 0x40005800": [struct.pack('<I', 0x40005800)],
    "AW PLAYCFG4  addr 0x09": [struct.pack('<H', 0x0009) + b'\x01'[:0], ],
    "AW CHIPID 0x57/0x58": [bytes([0x57, 0x58]), bytes([0x58, 0x57])],
}
NPLAIN = sum(ln for nm in ALL for (i, t, ln, x, r) in ALL[nm])
NP = sum(ln for nm in ALL for (i, t, ln, x, r) in ALL[nm] if nm == "本机2024")
print("4 份明文合计 %d B ；单份(本机) %d B" % (NPLAIN, NP))
print("%-26s %-11s %-11s %-13s %s" % ("模式", "4份明文命中", "期望(等长随机)", "倍数", "判定"))
for name, pats in PATS.items():
    hit = 0
    for nm in ALL:
        for (i, t, ln, x, r) in ALL[nm]:
            for p in pats:
                hit += x.count(p)
    exp = 0.0
    for _ in range(20):
        rb = os.urandom(NPLAIN)
        for p in pats:
            exp += rb.count(p)
    exp /= 20
    ratio = hit / exp if exp > 0 else float('inf') if hit else 0
    verdict = ("0 命中" if hit == 0 else
               ("≈随机 (%.2fx)" % ratio if 0.5 <= ratio <= 2 else
                ("★高于 %.1fx" % ratio if ratio > 2 else "★低于 %.2fx" % ratio)))
    print("%-26s %-11d %-11.2f %-13s %s" % (name, hit, exp, "%.2fx" % ratio, verdict))

print()
print("=" * 100)
print("【2】交叉比对：哪些块在不同芯片/版本里【逐字节相同】")
print("=" * 100)
names = list(SRC.keys())
for a in range(len(names)):
    for b2 in range(a + 1, len(names)):
        na, nb = names[a], names[b2]
        A, B = ALL[na], ALL[nb]
        same = []
        for i in range(min(len(A), len(B))):
            ia, ta, la, xa, ra = A[i]
            ib, tb, lb, xb, rb = B[i]
            if la == lb and xa == xb:
                same.append(i)
        # 也做全块集合比对（不看位置）
        setA = {x for (i, t, l, x, r) in A if l >= 0x1000}
        common = setA & {x for (i, t, l, x, r) in B if l >= 0x1000}
        if same or common:
            print("  %-9s vs %-9s : 同位置逐字节相同的块 = %s ；内容(不看位置)相同的大块 = %d"
                  % (na, nb, same, len(common)))

print()
print("=" * 100)
print("【3】这些数据到底是什么？—— 非零部分的分布形状")
print("=" * 100)
print("%-24s %-7s %-7s %-9s %-9s %-9s %-9s %s"
      % ("(固件/块)", "H0", "零%", "非零H0", "chi2(非零)", "u16众数占比", "u16 distinct", "形状"))
for nm in ["本机2024", "GT7863"]:
    for (i, t, ln, x, r) in ALL[nm]:
        nz = bytes(c for c in x if c != 0)
        if len(nz) < 500:
            print("%-24s %-7.3f %-7.2f %-9s %-9s %-9s %-9s %s"
                  % ("%s/块%d" % (nm, i), 0, 100, "-", "-", "-", "-", "空白"))
            continue
        e0 = -sum(v / len(nz) * math.log2(v / len(nz)) for v in collections.Counter(nz).values())
        exp = len(nz) / 256
        chi = sum((collections.Counter(nz).get(v, 0) - exp) ** 2 / exp for v in range(256))
        u16 = [int.from_bytes(x[j:j + 2], 'little') for j in range(0, ln - 1, 2)]
        c16 = collections.Counter(u16)
        mode = c16.most_common(1)[0][1] / len(u16) * 100
        shape = ("均匀(random-like)" if abs(chi - 255) < 120 else
                 ("强偏斜(表/结构化)" if chi > 1500 else "中等偏斜"))
        print("%-24s %-7.3f %-7.2f %-9.3f %-9.1f %-9.2f %-9d %s"
              % ("%s/块%d t=0x%02x" % (nm, i, t), 0, 100 * x.count(0) / ln,
                 e0, chi, mode, len(c16), shape))

print()
print("=" * 100)
print("【4】决定性测试：明文里还有没有【第二层】1024 周期 XOR？")
print("=" * 100)
for nm in ["本机2024"]:
    tot = b"".join(x for (i, t, l, x, r) in ALL[nm])
    def H(b):
        c = collections.Counter(b)
        return -sum(v / len(b) * math.log2(v / len(b)) for v in c.values())
    base = H(tot)
    best = []
    for ph in range(1024):
        d = bytes(v ^ K[(i + ph) % 1024] for i, v in enumerate(tot))
        best.append((H(d), ph))
    best.sort()
    print("  明文整体 H0 = %.4f" % base)
    print("  再 XOR K 各相位后 最优 H0 = %.4f @p=%d ；次优 %.4f ；均值 %.4f"
          % (best[0][0], best[0][1], best[1][0], sum(b[0] for b in best) / 1024))
    print("  ⇒ 若最优 H0 与均值差 < 0.05，说明【没有第二层】（第一层时该差为 %.3f）"
          % (base - min(b[0] for b in best)))

print()
print("=" * 100)
print("【5】压缩/编码测试（对明文，不只对加扰区）")
print("=" * 100)
import zlib, lzma, bz2
for nm in ["本机2024"]:
    for (i, t, ln, x, r) in ALL[nm]:
        if x.count(0) / ln > 0.9:
            continue
        z = len(zlib.compress(x, 9)) / ln
        l = len(lzma.compress(x)) / ln
        bz = len(bz2.compress(x)) / ln
        print("  块%-2d t=0x%02x 0x%05X  zlib=%.4f lzma=%.4f bz2=%.4f   %s"
              % (i, t, ln, z, l, bz, "★可压" if min(z, l, bz) < 0.90 else "不可压(非压缩数据)"))
