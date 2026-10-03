# win_opcode_xref.py — 读窗口里的结构 ↔ A0/A1 opcode 表 对照（纯本地）
#   问题：窗口里那簇 0xNN00 形状的编码，是不是同一套「参数/命令编号」？
import io, re, math, struct

POC = r"<LAB>\touchpad-lab\poc"
A0 = [0x01,0x05,0x0B,0x0D,0x0E,0x11,0x12,0x14,0x17,0x1F,0x20,0x24,0x26,0x32,0x33,0x35]
A1 = [0x02,0x04,0x07,0x08,0x0A,0x0B,0x0F,0x13,0x15,0x16,0x18,0x1D,0x23,0x28,0x29,0x2B,0x2C,0x2E,0x32,0x34,0x35,0x36]

def load(fn):
    mem = {}
    for ln in io.open(POC + "\\" + fn, encoding="utf-8-sig", errors="ignore"):
        m = re.match(r"^0x([0-9A-Fa-f]{4})\s+((?:[0-9A-Fa-f]{2}\s*)+)$", ln.strip())
        if m:
            mem[int(m.group(1), 16)] = bytes(int(x, 16) for x in m.group(2).split())
    lo = min(mem); hi = max(mem) + len(mem[max(mem)])
    buf = bytearray(b"\x00" * (hi - lo))
    for a, bs in mem.items():
        buf[a - lo:a - lo + len(bs)] = bs
    return bytes(buf), lo

A, loA = load("snapA.txt")
B, loB = load("snapB.txt")
print("snapA %d B (0x%04X起)   snapB %d B" % (len(A), loA, len(B)))
print()

# ─────────────────────────────────────────────────────────────
print("=" * 88)
print("① 全窗口扫描：形如 0xNN00 的 16 位值（NN=1..0x3F）")
print("=" * 88)
def scan_nn00(buf, endian):
    out = []
    fmt = "<H" if endian == "LE" else ">H"
    for off in range(0, len(buf) - 1, 2):
        v = struct.unpack_from(fmt, buf, off)[0]
        if v & 0xFF == 0 and 0x0100 <= v <= 0x3F00:
            out.append((off, v))
    return out

for endian in ("LE", "BE"):
    hits = scan_nn00(A, endian)
    nns = sorted(set(v >> 8 for _, v in hits))
    inA0 = [n for n in nns if n in A0]
    inA1 = [n for n in nns if n in A1]
    print("\n  %s: 命中 %d 处；出现的 NN 值 %d 个：%s" % (
        endian, len(hits), len(nns), " ".join("%02X" % n for n in nns)))
    print("       ∈ A0 的: %s" % (" ".join("%02X" % n for n in inA0) or "无"))
    print("       ∈ A1 的: %s" % (" ".join("%02X" % n for n in inA1) or "无"))
    print("       A0 覆盖 %d/%d   A1 覆盖 %d/%d" % (len(inA0), len(A0), len(inA1), len(A1)))
    # 位置分布
    print("       位置（前 30）: %s" % " ".join("%04X" % (loA + o) for o, _ in hits[:30]))

# ─────────────────────────────────────────────────────────────
print()
print("=" * 88)
print("② 那簇编码区 0x6C40..0x7060 原样 dump + 解析")
print("=" * 88)
s = 0x6C40 - loA; e = 0x7060 - loA
for off in range(s, min(e, len(A)), 16):
    row = A[off:off + 16]
    if not row: break
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print("0x%04X  %-47s |%s|" % (loA + off, " ".join("%02X" % b for b in row), asc))
print("\n  按 u16 LE 解析:")
vals = []
for off in range(s, min(e, len(A)) - 1, 2):
    v = struct.unpack_from("<H", A, off)[0]
    vals.append(v)
print("   ", " ".join("%04X" % v for v in vals[:48]))
print("  按 u16 BE 解析:")
vals2 = [struct.unpack_from(">H", A, o)[0] for o in range(s, min(e, len(A)) - 1, 2)]
print("   ", " ".join("%04X" % v for v in vals2[:48]))
print("  按 u32 LE 解析:")
v32 = [struct.unpack_from("<I", A, o)[0] for o in range(s, min(e, len(A)) - 3, 4)]
print("   ", " ".join("%08X" % v for v in v32[:24]))

# ─────────────────────────────────────────────────────────────
print()
print("=" * 88)
print("③ 活跃带 0x4560..0x4B00：0x77 打头的记录，求步长")
print("=" * 88)
band = A[0x4560 - loA:0x4B00 - loA]
pos = [i for i, b in enumerate(band) if b == 0x77]
print("  0x77 出现 %d 次；相邻位置差值（取众数看步长）:" % len(pos))
from collections import Counter
gaps = Counter(pos[i+1] - pos[i] for i in range(len(pos) - 1))
print("   ", gaps.most_common(10))
print("  前 64 字节:")
for off in range(0, min(64, len(band)), 16):
    row = band[off:off + 16]
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print("    0x%04X  %-47s |%s|" % (0x4560 + off, " ".join("%02X" % b for b in row), asc))
print("  按 u16 LE 取前 32 个值:", " ".join("%04X" % struct.unpack_from("<H", band, i)[0] for i in range(0, 64, 2)))

# ─────────────────────────────────────────────────────────────
print()
print("=" * 88)
print("④ 0x1000..0x4000 的分槽结构（每 512B 一行）")
print("=" * 88)
print("  地址      非零%  熵    首 8 字节")
for base in range(0x1000, 0x4000, 0x200):
    d = A[base - loA:base - loA + 0x200]
    nz = 100.0 * sum(1 for b in d if b) / len(d)
    c = [0]*256
    for b in d: c[b] += 1
    ent = 0.0
    for x in c:
        if x:
            p = x/len(d); ent -= p*math.log2(p)
    print("  0x%04X   %5.1f  %5.2f  %s" % (base, nz, ent, " ".join("%02X" % b for b in d[:8])))

# ─────────────────────────────────────────────────────────────
print()
print("=" * 88)
print("⑤ 稳定高熵块：是不是 IEEE754 浮点？（四种解释都算一遍）")
print("=" * 88)
blocks = [(0x41B4, 16), (0x4238, 8), (0x4240, 8), (0x4248, 12),
          (0x4344, 16), (0x6170, 16), (0x8000, 16)]
for addr, n in blocks:
    d = A[addr - loA:addr - loA + n]
    fl_le = [struct.unpack_from("<f", d, i)[0] for i in range(0, n - 3, 4)]
    fl_be = [struct.unpack_from(">f", d, i)[0] for i in range(0, n - 3, 4)]
    u32le = [struct.unpack_from("<I", d, i)[0] for i in range(0, n - 3, 4)]
    print("  0x%04X  %s" % (addr, " ".join("%02X" % b for b in d)))
    print("        u32LE : %s" % " ".join("%10d" % v for v in u32le))
    print("        f32LE : %s" % " ".join("%10.4g" % v for v in fl_le))
    print("        f32BE : %s" % " ".join("%10.4g" % v for v in fl_be))
