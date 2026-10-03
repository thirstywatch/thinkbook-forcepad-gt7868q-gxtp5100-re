# -*- coding: utf-8 -*-
"""
0x1E000 分段定性：
 1. 逐 512 B 窗口的 熵 / 零占比 / 高频字节
 2. 8051 指令结构检验（查表法，含操作数合法性）
 3. ARM Thumb 指令结构检验（BL/BX LR/DMB 等强特征）
 4. 定位 c2f2 密集子段与 88 42 子段
"""
import os, math, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "region_1E000_seg.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

w("=" * 80)
w("0x1E000 分段定性")
w("=" * 80); w()

SEG = data[0x1E000:0x20000]

def H(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())

w("【1】逐 512 B 窗口")
w("  偏移      熵      零占比  0x90占比 0xE7占比 0xF2占比 最高频")
for o in range(0, len(SEG), 512):
    win = SEG[o:o+512]
    c = collections.Counter(win)
    top = c.most_common(1)[0]
    w("  0x%05X  %.3f   %.3f   %.3f   %.3f   %.3f   0x%02X:%d"
      % (0x1E000+o, H(win), win.count(0)/len(win),
         win.count(0x90)/len(win), win.count(0xE7)/len(win), win.count(0xF2)/len(win),
         top[0], top[1]))
w()

# ---- 8051 严格指令表 ----
# (opcode, n_operand_bytes)
OPS_8051 = {}
for x in (0x00,0x03,0x04,0x05,0x13,0x14,0x15,0x23,0x24,0x25,0x33,0x34,0x35,
          0x43,0x44,0x45,0x53,0x54,0x55,0x63,0x64,0x65,0x73,0x74,0x75,
          0x83,0x84,0x85,0x93,0x94,0x95,0xA3,0xA4,0xA5,0xB3,0xB4,0xB5,
          0xC3,0xC4,0xC5,0xD3,0xD4,0xD5,0xE3,0xE4,0xE5,0xF3,0xF4,0xF5):
    OPS_8051[x] = 1
for x in (0x02,0x12,0x22,0x32,0x42,0x52,0x62,0x72,0x82,0x92,0xA2,0xB2,0xC2,0xD2,0xE2,0xF2):
    OPS_8051[x] = 1
for x in (0x01,0x21,0x41,0x61,0x81,0xA1,0xC1,0xE1,0x11,0x31,0x51,0x71,0x91,0xB1,0xD1,0xF1,0x80):
    OPS_8051[x] = 1
for x in (0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x90,0xA0,0xB0,0xC0,0xD0,0xE0,0xF0):
    OPS_8051[x] = 1
for x in (0xE6,0xE7,0xF6,0xF7,0x06,0x07,0x16,0x17,0x26,0x27,0x36,0x37,
          0xC6,0xC7,0xD6,0xD7,0xA6,0xA7,0xB6,0xB7,
          0x76,0x77,0x86,0x87,0x96,0x97,0xE8,0xE9,0xEA,0xEB,0xEC,0xED,0xEE,0xEF,
          0xF8,0xF9,0xFA,0xFB,0xFC,0xFD,0xFE,0xFF,
          0x28,0x29,0x2A,0x2B,0x2C,0x2D,0x2E,0x2F,
          0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,
          0x48,0x49,0x4A,0x4B,0x4C,0x4D,0x4E,0x4F,
          0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F,
          0x68,0x69,0x6A,0x6B,0x6C,0x6D,0x6E,0x6F,
          0x78,0x79,0x7A,0x7B,0x7C,0x7D,0x7E,0x7F):
    OPS_8051[x] = 1

def decode_8051(b, start=0):
    """返回 (已解码指令数, 消耗字节数)。严格：必须从 start 连续解到底或遇非法"""
    i = start; n = 0
    illegal = 0
    while i < len(b):
        op = b[i]
        if op not in OPS_8051:
            illegal += 1
            if illegal > 3: break
            i += 1
            continue
        i += 1 + OPS_8051[op]
        n += 1
    return n, i

w("【2】8051 结构检验（严格：非法操作码容忍 <=3）")
for name, off, size in [("0x00000 真代码", 0x00000, 4096),
                        ("0x19000 官方CFG", 0x19000, 4096),
                        ("0x1E000 起点", 0x1E000, 4096),
                        ("0x1E000 中段", 0x1E400, 4096),
                        ("0x1E000 尾段", 0x1F000, 4096),
                        ("0x1F120 ARM段", 0x1F120, 512),
                        ("0x04000 白化区", 0x04000, 4096)]:
    b = data[off:off+size]
    n, used = decode_8051(b, 0)
    w("  %-16s 解出 %4d 条 / 消耗 %4d / %4d B   覆盖率 %.3f"
      % (name, n, used, size, used/size))
w()

w("【3】ARM Thumb 强特征扫描（32-bit thumb2 指令首半字）")
ARM_STRONG = {
    0xF000: "BL/BLX (thumb2 前缀)", 0xF3BF: "DMB/DSB/ISB", 0xF04F: "MOV.W Rd,#imm",
    0xF240: "MOVW", 0xF2C0: "MOVT", 0xF8DF: "LDR.W Rd,[PC,#imm]", 0xF8D0: "LDR.W Rd,[Rn,#imm]",
    0xF8C0: "STR.W Rd,[Rn,#imm]", 0xF000: "BL", 0xF36F: "BFI",
}
def arm_count(b):
    c = 0; hits = collections.Counter()
    for i in range(0, len(b)-1, 2):
        hw = b[i] | (b[i+1] << 8)
        hi = hw & 0xFF00
        if hi in (0xF000, 0xF100, 0xF200, 0xF300, 0xF400, 0xF500, 0xF600, 0xF700,
                  0xF800, 0xF900, 0xFA00, 0xFB00):
            c += 1
            hits["%04X" % (hi)] += 1
    return c, hits

for name, off, size in [("0x1E000 全段", 0x1E000, 8192),
                        ("0x00000 真代码", 0x00000, 4096),
                        ("0x19000 官方CFG", 0x19000, 8192),
                        ("0x04000 白化区", 0x04000, 8192)]:
    b = data[off:off+size]
    c, hits = arm_count(b)
    w("  %-16s Thumb2 首半字命中 %4d / %d  (%.4f)  类型: %s"
      % (name, c, size//2, c/(size//2), dict(hits.most_common(5))))
w()

w("【4】已知 ARM 片段核验")
for pat, desc in [(b"\x70\x47", "BX LR (函数返回)"),
                  (b"\xbf\xf3\x4f\x8f", "DMB ISH"),
                  (b"\x80\xb5", "PUSH {R7,LR}"),
                  (b"\x00\xbf", "NOP"),
                  (b"\x08\xb0", "ADD SP,#32"),
                  (b"\x2d\xe9", "PUSH.W (thumb2)"),
                  (b"\x4f\xf4", "MOV.W 系列")]:
    pos = []
    i = 0
    while True:
        j = data.find(pat, i)
        if j < 0: break
        pos.append(j); i = j + 1
    in1e = [p for p in pos if 0x1E000 <= p < 0x20000]
    w("  %-22s 全固件 %3d 次, 其中 0x1E000 区内 %d 次" % (desc, len(pos), len(in1e)))
w()

w("【5】子段定位")
for pat, desc in [(b"\xc2\xf2", "c2 f2"), (b"\x88\x42", "88 42"),
                  (b"\xff\xe7", "ff e7"), (b"\xbd\xf8", "bd f8")]:
    pos = [i for i in range(0x1E000, 0x20000-1) if data[i:i+2] == pat]
    if pos:
        w("  %-8s 出现 %4d 次  ·  首 %s  ·  末 0x%X"
          % (desc, len(pos), "0x%X" % pos[0], pos[-1]))
        # 分区段密度
        buckets = collections.Counter((p-0x1E000)//1024 for p in pos)
        w("           每 1 KB 桶: %s" % sorted(buckets.items()))
    else:
        w("  %-8s 无" % desc)
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
