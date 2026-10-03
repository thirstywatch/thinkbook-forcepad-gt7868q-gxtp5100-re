# -*- coding: utf-8 -*-
"""
0x1E000 指令宽度判定 + 解码尝试
关键线索：ff e7 高频(292)、44 f2 / c2 f2 / bd f8 固定对高频
假设 A: 4 字节指令（首字节=操作码，后 3 字节操作数）——固定字长 MCU
假设 B: 2 字节指令（u16 LE 操作码）
假设 C: 变长 8051（已否）
检验法：对每种假设，看"操作码字段"是否集中在小值域（=真指令集），
        以及"操作数字段"是否接近均匀（=真数据）。
"""
import os, math, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "region_1E000_instr.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

SEG = data[0x1E000:0x20000]
N = len(SEG)

w("=" * 80)
w("0x1E000 指令宽度判定")
w("=" * 80); w()

def H(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())

def op_field_report(name, slots):
    """slots: list of (opcode_bytes, operand_bytes)"""
    ops = b"".join(s[0] for s in slots)
    opd = b"".join(s[1] for s in slots)
    co = collections.Counter(ops); cd = collections.Counter(opd)
    w("  %-28s 操作码熵 %.3f  操作数熵 %.3f  操作码种类 %3d/%d"
      % (name, H(ops), H(opd), len(co), 256 if len(ops[0:1])==1 else 65536))
    if len(ops) > 0 and len(co) <= 40:
        w("      操作码分布: %s" % ", ".join("0x%02X:%d" % (b, n) for b, n in co.most_common(40)))
    else:
        w("      操作码 Top-16: %s" % ", ".join("0x%02X:%d" % (b, n) for b, n in co.most_common(16)))
    return H(ops), H(opd)

w("【A】固定 4 字节指令假设（第 1 字节 = 操作码）")
slots = [(SEG[i:i+1], SEG[i+1:i+4]) for i in range(0, N-3, 4)]
op_field_report("4B: op=byte0, arg=byte1-3", slots)
w()

w("【B】固定 2 字节指令假设（u16 LE）")
lo = bytes(SEG[i] for i in range(0, N-1, 2))
hi = bytes(SEG[i+1] for i in range(0, N-1, 2))
w("  低字节熵 %.3f  高字节熵 %.3f" % (H(lo), H(hi)))
w("  低字节 Top-12: %s" % ", ".join("0x%02X:%d" % (b, n) for b, n in collections.Counter(lo).most_common(12)))
w("  高字节 Top-12: %s" % ", ".join("0x%02X:%d" % (b, n) for b, n in collections.Counter(hi).most_common(12)))
w()

w("【C】4 字节指令 · 首字节集中度检验（真实 MCU 操作码应集中在少数值）")
b0 = bytes(SEG[i] for i in range(0, N-3, 4))
b1 = bytes(SEG[i+1] for i in range(0, N-3, 4))
b2 = bytes(SEG[i+2] for i in range(0, N-3, 4))
b3 = bytes(SEG[i+3] for i in range(0, N-3, 4))
for nm, bb in [("byte0", b0), ("byte1", b1), ("byte2", b2), ("byte3", b3)]:
    c = collections.Counter(bb)
    top8 = sum(n for _, n in c.most_common(8)) / len(bb)
    w("  %s 熵 %.3f  种类 %3d  Top8 覆盖 %.3f" % (nm, H(bb), len(c), top8))
w()

w("【D】高频 4 字节块 top-30（找指令重复模式）")
blk = collections.Counter(SEG[i:i+4] for i in range(0, N-3, 4))
for k, v in blk.most_common(30):
    w("    %s  ×%d" % (k.hex(" "), v))
w()

w("【E】高频 4 字节块（滑动，允许任意对齐）top-30")
blk2 = collections.Counter(SEG[i:i+4] for i in range(0, N-3))
for k, v in blk2.most_common(30):
    w("    %s  ×%d" % (k.hex(" "), v))
w()

w("【F】ff e7 上下文（出现 292 次的那个高频对）")
pos = [i for i in range(N-1) if SEG[i] == 0xFF and SEG[i+1] == 0xE7]
w("  ff e7 出现 %d 次" % len(pos))
w("  两侧 32 B 取值（前 6 处）:")
for p in pos[:6]:
    a = max(0, p-16); b = min(N, p+16)
    w("    @+0x%05X  %s   [ff e7]   %s"
      % (0x1E000+p, SEG[a:p].hex(" "), SEG[p+2:b].hex(" ")))
w()
w("  ff e7 后一字节分布: %s" % ", ".join(
    "0x%02X:%d" % (b, n) for b, n in collections.Counter(SEG[p+2] for p in pos if p+2 < N).most_common(12)))
w("  ff e7 前一字节分布: %s" % ", ".join(
    "0x%02X:%d" % (b, n) for b, n in collections.Counter(SEG[p-1] for p in pos if p >= 1).most_common(12)))
w()

w("【G】44 f2 / c2 f2 / bd f8 后缀分布（判是否为双字节操作码+双字节操作数）")
for pat, nm in [(b"\x44\xf2", "44 f2"), (b"\xc2\xf2", "c2 f2"), (b"\xbd\xf8", "bd f8"),
                (b"\x44\xf6", "44 f6"), (b"\x8d\xf8", "8d f8"), (b"\x30\xf9", "30 f9")]:
    pp = [i for i in range(N-1) if SEG[i:i+2] == pat]
    if not pp: 
        w("  %s: 0 次" % nm); continue
    nxt = collections.Counter(SEG[p+2] for p in pp if p+2 < N)
    w("  %s ×%-4d  第3字节 Top-8: %s" % (nm, len(pp),
      ", ".join("0x%02X:%d" % (b, n) for b, n in nxt.most_common(8))))
w()

w("【H】按 4 字节分组后，看 u32 值是否像地址（递增/成簇）")
u32 = [int.from_bytes(SEG[i:i+4], "little") for i in range(0, N-3, 4)]
srt = sorted(u32)
# 看数值分布的量级
import bisect
for lo_, hi_ in [(0, 0x100), (0x100, 0x1000), (0x1000, 0x10000), (0x10000, 0x100000),
                 (0x100000, 0x1000000), (0x1000000, 0x10000000), (0x10000000, 0x100000000)]:
    n = sum(1 for v in u32 if lo_ <= v < hi_)
    w("  [0x%08X, 0x%08X) : %5d  (%.3f)" % (lo_, hi_, n, n/len(u32)))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
