# -*- coding: utf-8 -*-
"""
0x1E000 指令集识别 —— 横向比对 + 结构度量
 1. 双字节操作码假设（大端 u16）
 2. 与 tpfw.bin（明文 G1_7863, 86272 B）做同样的度量，看是否存在"同款 ISA"
 3. 与 0x00000（已确认明文 8051 真代码）对照
 4. 指令长度分布估计：用"操作码字典"迭代法
"""
import os, math, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
TPFW = r"<WORKSPACE>"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "region_1E000_isa.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

def H(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())

w("=" * 80)
w("0x1E000 指令集识别")
w("=" * 80); w()

SEG = data[0x1E000:0x20000]
N = len(SEG)

w("【1】双字节操作码假设：big-endian u16")
hi2 = bytes(SEG[i] for i in range(0, N-1, 2))
lo2 = bytes(SEG[i+1] for i in range(0, N-1, 2))
c_hi = collections.Counter(hi2)
w("  u16 高字节熵 %.3f  种类 %d" % (H(hi2), len(c_hi)))
w("  u16 高字节 Top-16: %s"
  % ", ".join("0x%02X:%d" % (b, n) for b, n in c_hi.most_common(16)))
# 双字节操作码的候选：高字节集中
top_cov = sum(n for _, n in c_hi.most_common(16)) / len(hi2)
w("  高字节 Top-16 覆盖 %.3f" % top_cov)
w()

w("【2】三份样本的字节级结构度量对照")
def metrics(name, b):
    N2 = len(b)
    c = collections.Counter(b)
    p0 = c.most_common(1)[0][1] / N2
    # 相邻字节"同列集中度"（按 2 字节列）
    col_a = bytes(b[i] for i in range(0, N2-1, 2))
    col_b = bytes(b[i+1] for i in range(0, N2-1, 2))
    ca = collections.Counter(col_a); cb = collections.Counter(col_b)
    w("  %-22s 熵 %.3f  top1占比 %.3f | 偶列熵 %.3f Top8 %.3f | 奇列熵 %.3f Top8 %.3f"
      % (name, H(b), p0, H(col_a),
         sum(n for _, n in ca.most_common(8))/len(col_a),
         H(col_b),
         sum(n for _, n in cb.most_common(8))/len(col_b)))
    return H(b)

metrics("0x1E000 (8 KB)", SEG)
metrics("0x00000 真代码 4KB", data[0x00000:0x01000])
metrics("0x19000 官方CFG 8KB", data[0x19000:0x1A000])
metrics("0x04000 白化区 8KB", data[0x04000:0x06000])
if os.path.exists(TPFW):
    t = open(TPFW, "rb").read()
    w("  tpfw.bin 总长 %d B" % len(t))
    # 找它的代码区（低熵段）
    for off in (0x00000, 0x01000, 0x02000, 0x04000, 0x08000, 0x10000):
        if off + 0x2000 <= len(t):
            metrics("tpfw@0x%05X" % off, t[off:off+0x2000])
else:
    w("  (tpfw.bin 不存在)")
w()

w("【3】操作码字典收敛法（估指令长度）")
def dict_converge(b, maxlen=4, rounds=6):
    """迭代：把最高频的 n-gram 当作'指令'，看覆盖率何时收敛"""
    res = []
    for nlen in range(1, maxlen+1):
        grams = collections.Counter(b[i:i+nlen] for i in range(0, len(b)-nlen+1))
        # 用贪心切分：从左到右，优先匹配最长已知高频 gram
        for thresh in (2,):
            top = [g for g, n in grams.most_common(64) if n >= thresh]
            top.sort(key=len, reverse=True)
            i = 0; covered = 0; ninstr = 0
            while i < len(b):
                matched = None
                for g in top:
                    if b[i:i+len(g)] == g:
                        matched = g; break
                if matched:
                    i += len(matched); covered += len(matched); ninstr += 1
                else:
                    i += 1
            res.append((nlen, len(top), covered/len(b), ninstr))
    return res

for nm, b in [("0x1E000", SEG[:8192]), ("0x00000 真代码", data[:4096])]:
    w("  %s:" % nm)
    for nlen, ntop, cov, ninstr in dict_converge(b):
        w("     gram 长度 %d  词典 %d 项  覆盖率 %.3f  指令数 %d" % (nlen, ntop, cov, ninstr))
w()

w("【4】0x1E000 的对齐自洽性：按 2/4 字节处理时，'明显指令串'能否延续")
# 手动检查若干候选指令串
for base in (0x1E01C, 0x1E024, 0x1E03C, 0x1F120, 0x1F1C0, 0x1F3C0):
    o = base - 0x1E000
    seg = SEG[o:o+48]
    w("  @0x%05X  %s" % (base, seg.hex(" ")))
w()

w("【5】ff e7 与 bd f8 是否为同一指令的两种形态？")
# ff e7 = 11111111 11100111 → 若视为 u16 LE = 0xE7FF
# bd f8 = 10111101 11111000 → 0xF8BD
w("  ff e7 → u16LE 0xE7FF / u16BE 0xFFE7")
w("  bd f8 → u16LE 0xF8BD / u16BE 0xBDF8")
w("  注意: 0xE7FF 与 0xF8BD 都出现在 u16 高频表中")
u16le = [int.from_bytes(SEG[i:i+2], "little") for i in range(0, N-1, 2)]
c16 = collections.Counter(u16le)
w("  u16LE Top-20: %s" % ", ".join("0x%04X:%d" % (v, n) for v, n in c16.most_common(20)))
tot = len(u16le)
top20 = sum(n for _, n in c16.most_common(20)) / tot
w("  18 位 u16 值 Top-20 覆盖 %.3f  (随机期望 %.5f)" % (top20, 20/65536))
w()

w("【6】疑似 Goodix 自研核：与已知 ISA 特征串比对")
KNOWN = {
    "ARM Thumb BX LR (70 47)": b"\x70\x47",
    "ARM PUSH {R7,LR} (80 b5)": b"\x80\xb5",
    "8051 LJMP (02 xx xx)": None,
    "Xtensa RET (f0 00)": b"\xf0\x00",
    "RISC-V C.J / c.ret": None,
}
for k, v in KNOWN.items():
    if v is None:
        w("  %-28s  (跳过，需上下文)" % k); continue
    n = 0; i = 0
    while True:
        j = SEG.find(v, i)
        if j < 0: break
        n += 1; i = j+1
    w("  %-28s 命中 %d" % (k, n))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
