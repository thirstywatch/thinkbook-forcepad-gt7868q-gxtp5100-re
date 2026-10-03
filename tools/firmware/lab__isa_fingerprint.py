# -*- coding: utf-8 -*-
"""载荷A 13 块【明文】的指令集指纹 —— 用真反汇编器 capstone
2026-10-02
"""
import struct, collections, math, os
from capstone import *

KWIN = "<WORKSPACE>"
K = open(KWIN, 'rb').read()


def rotl(k, n):
    n %= len(k)
    return k[n:] + k[:n]


K316 = rotl(K, 316)


def entropy(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum(v / n * math.log2(v / n) for v in c.values()) if n else 0.0


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


md_thumb = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
md_arm = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md_rv = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32)


def cov(md, b, al, limit=4096):
    """线性扫描：成功连续消费的字节比例"""
    off = 0
    ok = 0
    for ins in md.disasm(b[:limit], 0):
        if ins.address != off:
            break
        off += ins.size
        ok += 1
    return ok * al / limit


def halfhist(b):
    """16 位半字高字节集中度：真代码 top8 占 40%+；随机 ~5%"""
    ev = collections.Counter(b[0::2])
    od = collections.Counter(b[1::2])
    def peak(c, n):
        return sum(sorted(c.values(), reverse=True)[:8]) / n * 100
    return peak(ev, len(b[0::2])), peak(od, len(b[1::2]))


OPS8051 = {0x02, 0x12, 0x22, 0x32, 0x74, 0x75, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D,
           0x7E, 0x7F, 0x90, 0xE4, 0xE5, 0xF0, 0xD2, 0xC2, 0xA3, 0x80, 0x70, 0x60,
           0x50, 0x40, 0x20, 0x30, 0xB4, 0xB5, 0x05, 0x15, 0x25, 0x35, 0x45, 0x85,
           0xE0, 0xA5}


def row(name, b, tag=""):
    t = cov(md_thumb, b, 2)
    a = cov(md_arm, b, 4)
    r = cov(md_rv, b, 4) if md_rv else 0
    ev, od = halfhist(b)
    oh = sum(1 for c in b if c in OPS8051) / len(b) * 100
    print("%-26s %-8.4f %-9.1f %-9.1f %-9.1f %-10.1f %-9.1f %s"
          % (name, entropy(b), t * 100, a * 100, r * 100, (ev + od) / 2, oh, tag))
    return (t, a, r, (ev + od) / 2)


print("=" * 104)
print("【基线】真代码 与 随机")
print("%-26s %-8s %-9s %-9s %-9s %-10s %-9s %s"
      % ("样本", "H0", "Thumb%", "ARM%", "RISC-V%", "半字top8%", "8051密集%", "说明"))
tf = open("<WORKSPACE>", 'rb').read()
row("TF100A 0x8000(真Thumb)", tf[0x8000:0xA000], "← 代码基线")
row("TF100A 0x0000(向量表)", tf[0x0000:0x0100], "← 向量表")
gx = open("bios-re/GoodixTpDxe.bin", 'rb').read()
row("GoodixTpDxe 0x1000(真x86)", gx[0x1000:0x3000], "← 代码基线")
row("随机 os.urandom", os.urandom(0x2000), "← 随机基线")
row("本机 raw(未解扰)", open("bios-re/GT7868Q_native_fw.bin", 'rb').read()[0x123C:0x123C + 0x2000],
    "← 加扰基线")

print("=" * 104)
print("★ 本机 GT7868Q 的 13 块【明文】(plain = raw ^ rot_left(K,316)[容器相对])")
print("%-26s %-8s %-9s %-9s %-9s %-10s %-9s %s"
      % ("块", "H0", "Thumb%", "ARM%", "RISC-V%", "半字top8%", "8051密集%", "判定"))
buf = open("bios-re/GT7868Q_native_fw.bin", 'rb').read()
o, ent = parse(buf)
off = o + 0x100
acc = []
for i, (t, ln) in enumerate(ent):
    xr = buf[off:off + ln]
    off += ln
    x = bytes(v ^ K316[(k + 0x100) % 1024] for k, v in enumerate(xr))
    v = row("块%-2d type=0x%02x 0x%05X" % (i, t, ln), x,
            "空白" if entropy(x) < 4 else ("★像代码?" if cov(md_thumb, x, 2) > 0.5 else "数据"))
    acc.append(v)
n = len(acc)
print("-" * 104)
print("13 块平均：Thumb 覆盖 %.1f%%   ARM %.1f%%   RISC-V %.1f%%   半字top8 %.1f%%"
      % (sum(a[0] for a in acc) / n * 100, sum(a[1] for a in acc) / n * 100,
         sum(a[2] for a in acc) / n * 100, sum(a[3] for a in acc) / n))
print()
print("⇒ 判定阈值（由上面基线标定）：Thumb 覆盖 > 50% 且 半字top8 > 28% ⇒ 代码；否则数据")
