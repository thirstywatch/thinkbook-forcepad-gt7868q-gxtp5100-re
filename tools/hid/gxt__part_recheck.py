# -*- coding: utf-8 -*-
"""
0x1E000 矛盾的复核：
  A) 分区表解码自洽性检查（字段宽度 / 字节序 / 边界连续性）
  B) 固件里是否存在第二份分区表
  C) 各分区在文件里的真实字节内容（熵 / 操作码密度 / 首 32 B）
  D) 0x1E000 直方图 + 与"配置数据"应有的样子对照
"""
import os, sys, math, struct, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "part_recheck.txt")

data = open(FW, "rb").read()
L = len(data)
lines = []
def w(s=""):
    lines.append(s)
    print(s)

w("=" * 78)
w("0x1E000 矛盾复核  —— 固件 %d B" % L)
w("=" * 78)
w()

# ---------- A) 定位分区表 ----------
def find_table(buf, anchor=b"YELSTO"):
    pos = []
    i = 0
    while True:
        j = buf.find(anchor, i)
        if j < 0: break
        pos.append(j)
        i = j + 1
    return pos

w("【A】分区表定位")
yel = find_table(data)
w("  'YELSTO' 出现位置: %s" % ["0x%X" % p for p in yel])
for p in yel:
    t = p + 0x22
    w("  @0x%X + 0x22 = 0x%X 处的 16 字节: %s" % (p, t, data[t:t+16].hex(" ")))
w()

def parse_table(buf, off, n=13):
    rows = []
    for k in range(n):
        b = buf[off + k*8: off + k*8 + 8]
        if len(b) < 8: break
        typ = b[0]
        size_be = int.from_bytes(b[1:5], "big")
        addr_be = int.from_bytes(b[4:8], "big")
        rows.append((typ, size_be, addr_be, b.hex(" ")))
    return rows

TBL = None
for p in yel:
    off = p + 0x22
    rows = parse_table(data, off)
    # 判定条件：第一项 type 必须 0x03/0x02，size 必须是 2 的幂量级
    if rows and rows[0][0] in (0x02, 0x03) and rows[0][1] in (0x1000, 0x2000, 0x3000):
        TBL = (off, rows)
        break

if TBL is None:
    w("!! 未找到合法分区表")
    sys.exit(1)

off, rows = TBL
w("  选中表 @0x%X" % off)
w()
w("  idx type  size(BE)  flash_addr(BE)  原始 8 字节")
covered = {}
for k, (typ, size, addr, raw) in enumerate(rows):
    if size == 0 and addr == 0:
        w("  %2d  ----  表结束（全零）  raw=%s" % (k, raw)); break
    w("  %2d  0x%02X  %6d   0x%05X       %s" % (k, typ, size, addr, raw))
    covered[addr] = size
w()

# 自洽 1: 所有 flash_addr 是 0x1000 对齐？
bad_align = [a for a in covered if a % 0x1000 != 0]
w("  自洽检查 1 · 地址 0x1000 对齐 : %s" % ("全部通过" if not bad_align else "失败 %s" % bad_align))

# 自洽 2: size 都是 0x1000 倍数？
bad_size = [(a, s) for a, s in covered.items() if s % 0x1000 != 0]
w("  自洽检查 2 · 大小 0x1000 倍数 : %s" % ("全部通过" if not bad_size else "失败 %s" % bad_size))

# 自洽 3: 分区是否重叠
iv = sorted(covered.items())
ov = []
for i in range(len(iv)-1):
    e = iv[i][0] + iv[i][1]
    if e > iv[i+1][0]:
        ov.append((hex(iv[i][0]), hex(iv[i+1][0])))
w("  自洽检查 3 · 分区不重叠   : %s" % ("全部通过" if not ov else "重叠 %s" % ov))

# 自洽 4: 分区是否铺满 0x00000..0x20000
tot = sum(covered.values())
w("  自洽检查 4 · 覆盖总字节     : %d B (0x%X)；地址空间 0x00000..0x20000 = %d B"
  % (tot, tot, 0x20000))
w("               缺口           : %d B" % (0x20000 - tot))
w()

# ---------- B) 第二份分区表？ ----------
w("【B】是否存在第二份分区表")
hits = []
needle = data[off: off + 8*6]      # 前 6 项 48 字节
i = 0
while True:
    j = data.find(needle, i)
    if j < 0: break
    hits.append(j); i = j + 1
w("  前 48 字节(6 项)精确匹配位置: %s" % ["0x%X" % h for h in hits])
# 宽松匹配：只看 3 个分区描述
p3 = data[off: off + 24]
hits3 = []
i = 0
while True:
    j = data.find(p3, i)
    if j < 0: break
    hits3.append(j); i = j + 1
w("  前 24 字节(3 项)精确匹配位置: %s" % ["0x%X" % h for h in hits3])
w()

# ---------- C) 各分区真实内容 ----------
def H(b):
    if not b: return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum(v/n * math.log2(v/n) for v in c.values())

OPCODES = None
def opcode_density(b):
    """8051 常见单/双字节操作码集合（取 0x00-0xFF 中真实指令的集合，按 turbo51 文档）"""
    OPS = set()
    # 单字节
    for x in (0x00,0x03,0x04,0x05,0x13,0x14,0x15,0x23,0x24,0x25,0x33,0x34,0x35,
              0x43,0x44,0x45,0x53,0x54,0x55,0x63,0x64,0x65,0x73,0x74,0x75,
              0x83,0x84,0x85,0x93,0x94,0x95,0xA3,0xA4,0xA5,0xB3,0xB4,0xB5,
              0xC3,0xC4,0xC5,0xD3,0xD4,0xD5,0xE3,0xE4,0xE5,0xF3,0xF4,0xF5):
        OPS.add(x)
    for x in (0x02,0x12,0x22,0x32,0x42,0x52,0x62,0x72,0x82,0x92,0xA2,0xB2,
              0xC2,0xD2,0xE2,0xF2):
        OPS.add(x)
    for x in (0x01,0x21,0x41,0x61,0x81,0xA1,0xC1,0xE1,
              0x11,0x31,0x51,0x71,0x91,0xB1,0xD1,0xF1,0x80):
        OPS.add(x)
    for x in (0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x90,0xA0,0xB0,0xC0,0xD0,0xE0,0xF0,
              0xE6,0xE7,0xF6,0xF7,0x06,0x07,0x16,0x17,0x26,0x27,0x36,0x37,
              0xC6,0xC7,0xD6,0xD7,0xA6,0xA7,0xB6,0xB7,
              0x76,0x77,0x86,0x87,0x96,0x97,0xE8,0xE9,0xEA,0xEB,0xEC,0xED,0xEE,0xEF,
              0xF8,0xF9,0xFA,0xFB,0xFC,0xFD,0xFE,0xFF,
              0x28,0x29,0x2A,0x2B,0x2C,0x2D,0x2E,0x2F,
              0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,
              0x48,0x49,0x4A,0x4B,0x4C,0x4D,0x4E,0x4F,
              0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F,
              0x68,0x69,0x6A,0x6B,0x6C,0x6D,0x6E,0x6F,
              0x78,0x79,0x7A,0x7B,0x7C,0x7D,0x7E,0x7F):
        OPS.add(x)
    return sum(1 for x in b if x in OPS) / len(b)

w("【C】各分区在文件中的真实字节内容")
w("  addr    size   type  熵      操作码密度  0x00占比  首 24 字节")
for k, (typ, size, addr, raw) in enumerate(rows):
    if size == 0: break
    seg = data[addr:addr+size]
    if len(seg) == 0:
        w("  0x%05X  --     0x%02X  (超出文件范围)" % (addr, typ)); continue
    zf = seg.count(0) / len(seg)
    w("  0x%05X %6d  0x%02X  %.3f   %.4f     %.3f     %s"
      % (addr, size, typ, H(seg), opcode_density(seg), zf, seg[:24].hex(" ")))
w()

# 文件尾部之后是什么
w("  文件总长 0x%X；分区最高地址+size = 0x%X" % (L, max(a+s for a, s in covered.items())))
gap = L - max(a+s for a, s in covered.items())
w("  尾部剩余 %d B" % gap)
w()

# ---------- D) 0x1E000 深挖 ----------
w("【D】0x1E000 区（官方标注 FLASH_ADDR_CONFIG_DATA）深挖")
seg = data[0x1E000:0x20000]
w("  长度 %d B  熵 %.4f  操作码密度 %.4f" % (len(seg), H(seg), opcode_density(seg)))
c = collections.Counter(seg)
w("  最高频 12 个字节: %s" % ", ".join("0x%02X:%d" % (b, n) for b, n in c.most_common(12)))
w("  最低频 6 个字节 : %s" % ", ".join("0x%02X:%d" % (b, n) for b, n in c.most_common()[-6:]))
w("  不同字节值个数   : %d / 256" % len(c))
w()
w("  前 256 B 逐 16 字节:")
for o in range(0, 256, 16):
    w("    0x%05X  %s" % (0x1E000+o, seg[o:o+16].hex(" ")))
w()
w("  中间段 0x1F000 逐 16 字节:")
for o in range(0x1000, 0x1000+128, 16):
    w("    0x%05X  %s" % (0x1E000+o, seg[o:o+16].hex(" ")))
w()

# 与真正的明文代码区 0x00000 对照
w("  对照 · 0x00000 (真代码, 4096 B)：熵 %.3f 密度 %.4f 零占比 %.3f"
  % (H(data[:4096]), opcode_density(data[:4096]), data[:4096].count(0)/4096))
w("  对照 · 0x19000 (官方 CFG_FLASH_ADDR, 8192 B)：熵 %.3f 密度 %.4f 零占比 %.3f"
  % (H(data[0x19000:0x1A000]), opcode_density(data[0x19000:0x1A000]), data[0x19000:0x1A000].count(0)/8192))
w()

# 0x1E000 是否可能真的是"配置"：看它是否像 TLV / 结构体数组
w("  · 检测是否为 8 B 结构体数组（u16 字段模式）")
u16 = [int.from_bytes(seg[i:i+2], "little") for i in range(0, 4096, 2)]
cnt = collections.Counter(u16)
w("    前 2048 个 u16 中最高频: %s" % ", ".join("%d(0x%X):%d" % (v, v, n) for v, n in cnt.most_common(8)))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
