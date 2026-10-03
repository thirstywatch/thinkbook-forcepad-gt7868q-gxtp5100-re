# -*- coding: utf-8 -*-
"""严格零模型 + 数据类型命名
零模型：E[count] = N * f(b0)*f(b1)*f(b2)*f(b3)  —— f 为该数据集自身的字节频率
（这才是"这个位置出现这个字节"的正确期望；os.urandom 的零密度不匹配会造假阳性）
"""
import struct, collections, math, os

K = open("<WORKSPACE>", 'rb').read()
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
                t = buf[q]; ln = int.from_bytes(buf[q + 1:q + 5], 'big')
                if t == 0 and ln == 0: break
                ent.append((t, ln))
            return o, ent
    return None


def load(path):
    b = open(path, 'rb').read(); o, ent = parse(b); off = o + 0x100; out = []
    for i, (t, ln) in enumerate(ent):
        xr = b[off:off + ln]; off += ln
        out.append((i, t, ln, bytes(v ^ K316[(k + 0x100) % 1024] for k, v in enumerate(xr))))
    return out


ALL = {nm: load(p) for nm, p in SRC.items()}
TOT = b"".join(x for nm in ALL for (i, t, l, x) in ALL[nm])

print("=" * 104)
print("【1-严格】AW86927 / I²C 主机常量 —— 用【逐位置字节频率零模型】")
print("=" * 104)
N = len(TOT)
f = collections.Counter(TOT)
PATS = {
    "0x9270 BE": b'\x92\x70',
    "0x9270 LE": b'\x70\x92',
    "I2C CR1_START 0x00000100": struct.pack('<I', 0x100),
    "I2C CR1_STOP  0x00000200": struct.pack('<I', 0x200),
    "I2C CR1_ACK   0x00000400": struct.pack('<I', 0x400),
    "I2C CR1_SWRST 0x00008000": struct.pack('<I', 0x8000),
    "I2C CR1_POS   0x00000800": struct.pack('<I', 0x800),
    "I2C1 base 0x40005400": struct.pack('<I', 0x40005400),
    "I2C2 base 0x40005800": struct.pack('<I', 0x40005800),
    "SPI2  base 0x40003800": struct.pack('<I', 0x40003800),
    "AW RSTCFG 0xAA": bytes([0x00, 0xAA]),
}
print("样本 = 4 份明文合计 %d B" % N)
print("%-28s %-9s %-12s %-9s %-9s %s" % ("模式", "命中", "零模型期望", "Poisson z", "倍数", "判定"))
for nm, p in PATS.items():
    c = TOT.count(p)
    e = N
    for ch in p:
        e *= f.get(ch, 0) / N
    z = (c - e) / math.sqrt(e + 1e-9)
    verdict = ("≈随机" if abs(z) < 3 else ("★显著高于 (z=%.1f)" % z if z > 0 else "★显著低于"))
    print("%-28s %-9d %-12.3f %-9.2f %-9s %s" % (nm, c, e, z, "%.2fx" % (c / e if e > 0 else 0), verdict))

print()
print("=" * 104)
print("【2】数据类型判别：16 位小端结构 / 记录长度 / 高低字节分工")
print("=" * 104)
print("%-22s %-8s %-8s %-9s %-9s %-9s %-8s %s"
      % ("(固件/块)", "偶位H0", "奇位H0", "偶位top4%", "奇位top4%", "u16范围p99", "记录L", "判别"))
for nm in ["本机2024"]:
    for (i, t, ln, x) in ALL[nm]:
        ev, od = x[0::2], x[1::2]
        def H(b):
            if not b: return 0
            c = collections.Counter(b); n = len(b)
            return -sum(v / n * math.log2(v / n) for v in c.values())
        def top4(b):
            c = collections.Counter(b)
            return sum(sorted(c.values(), reverse=True)[:4]) / max(len(b), 1) * 100
        u16 = sorted(int.from_bytes(x[j:j + 2], 'little') for j in range(0, ln - 1, 2))
        p99 = u16[int(len(u16) * 0.99)] if u16 else 0
        # 记录长度：逐字节自相关，找 1..2048 里最高的
        best = (0, 0)
        for L in list(range(1, 65)) + [128, 256, 512, 1024, 2048]:
            if L >= ln: break
            r = sum(1 for j in range(ln - L) if x[j] == x[j + L]) / (ln - L)
            if r > best[0]: best = (r, L)
        # 判定
        if H(x) < 4: v = "空白"
        elif top4(od) > top4(ev) + 6 and H(od) < H(ev) - 0.15: v = "★16 位小端数据（奇位=高字节更结构化）"
        elif best[0] > 0.05: v = "★疑似定长记录 L=%d (match %.3f)" % (best[1], best[0])
        else: v = "高熵数值数据"
        print("%-22s %-8.3f %-8.3f %-9.2f %-9.2f %-9d %-8d %s"
              % ("块%d t=0x%02x 0x%05X" % (i, t, ln), H(ev), H(od), top4(ev), top4(od), p99, best[1], v))

print()
print("=" * 104)
print("【3】与真代码 / 真随机的可压比对照（用同一 zlib -9）")
print("=" * 104)
import zlib
tf = open("<WORKSPACE>", 'rb').read()
gx = open("bios-re/GoodixTpDxe.bin", 'rb').read()
for nm, b in [("TF100A 真Thumb代码 8K", tf[0x8000:0xA000]),
              ("GoodixTpDxe 真x86代码 8K", gx[0x1000:0x3000]),
              ("os.urandom 8K", os.urandom(0x2000)),
              ("本机 明文数据区 全 98KB", TOT[:100352]),
              ("本机 块0 (跨芯片共享)", ALL["本机2024"][0][3])]:
    print("  %-28s zlib可压比 = %.4f" % (nm, len(zlib.compress(b, 9)) / len(b)))
