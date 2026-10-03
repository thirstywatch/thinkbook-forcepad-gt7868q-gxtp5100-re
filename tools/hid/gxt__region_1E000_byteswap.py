# -*- coding: utf-8 -*-
"""
关键假设：0x1E000 是 8051 代码，但字节对存在交换（16 位字内高低字节互换）。
检验：把每 2 字节交换后再做 8051 严格解码，看覆盖率是否飙升。
同时对 0x00000（已知真代码）做同样处理作对照。
"""
import os, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "region_1E000_byteswap.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

w("=" * 80)
w("0x1E000 字节序假设检验")
w("=" * 80); w()

# 严格 8051 操作码长度表
LEN = {}
for x in (0x00,0x03,0x04,0x05,0x13,0x14,0x15,0x23,0x24,0x25,0x33,0x34,0x35,
          0x43,0x44,0x45,0x53,0x54,0x55,0x63,0x64,0x65,0x73,0x74,0x75,
          0x83,0x84,0x85,0x93,0x94,0x95,0xA3,0xA4,0xA5,0xB3,0xB4,0xB5,
          0xC3,0xC4,0xC5,0xD3,0xD4,0xD5,0xE3,0xE4,0xE5,0xF3,0xF4,0xF5):
    LEN[x] = 2                      # op, imm8
for x in (0x02,0x12,0x22,0x32,0x42,0x52,0x62,0x72,0x82,0x92,0xA2,0xB2,0xC2,0xD2,0xE2,0xF2):
    LEN[x] = 2                      # op, bit/rel
for x in (0x01,0x21,0x41,0x61,0x81,0xA1,0xC1,0xE1,0x11,0x31,0x51,0x71,0x91,0xB1,0xD1,0xF1,0x80):
    LEN[x] = 2                      # op, rel
for x in (0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x90,0xA0,0xB0,0xC0,0xD0,0xE0,0xF0):
    LEN[x] = 2                      # op, bit/direct
for x in (0xE6,0xE7,0xF6,0xF7,0x06,0x07,0x16,0x17,0x26,0x27,0x36,0x37,
          0xC6,0xC7,0xD6,0xD7,0xA6,0xA7,0xB6,0xB7,
          0x76,0x77,0x86,0x87,0x96,0x97,
          0x28,0x29,0x2A,0x2B,0x2C,0x2D,0x2E,0x2F,
          0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,
          0x48,0x49,0x4A,0x4B,0x4C,0x4D,0x4E,0x4F,
          0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F,
          0x68,0x69,0x6A,0x6B,0x6C,0x6D,0x6E,0x6F,
          0x78,0x79,0x7A,0x7B,0x7C,0x7D,0x7E,0x7F):
    LEN[x] = 1
# 真正的三字节指令（LCALL/LJMP）单独处理
for x in (0x02, 0x12):
    LEN[x] = 3
for x in (0xE8,0xE9,0xEA,0xEB,0xEC,0xED,0xEE,0xEF,
          0xF8,0xF9,0xFA,0xFB,0xFC,0xFD,0xFE,0xFF):
    LEN[x] = 1
# 其余单字节
for x in range(256):
    if x not in LEN:
        LEN[x] = 1

def seg_stats(b, nm):
    """严格顺序解码：从 0 开始，遇到无法解释就停；统计连续解出长度 + 非法率"""
    i = 0; n = 0; illegal = 0
    # 允许 3 次非法跳 1 字节，统计最长连续
    run = 0; bestrun = 0
    while i < len(b):
        op = b[i]
        step = LEN[op]
        if i + step > len(b): break
        i += step; n += 1; run += step
        if run > bestrun: bestrun = run
    return n, i

def check_seq(b, nm):
    """顺序解码（不容忍非法）——真代码可以从头解到尾"""
    i = 0; n = 0
    while i < len(b):
        op = b[i]
        step = LEN[op]
        if i + step > len(b):
            break
        i += step; n += 1
    cov = i / len(b)
    w("  %-34s 顺序解出 %5d 条 / 消耗 %5d / %5d B  覆盖 %.4f"
      % (nm, n, i, len(b), cov))
    return cov

def swap16(b):
    out = bytearray(len(b))
    for i in range(0, len(b)-1, 2):
        out[i] = b[i+1]; out[i+1] = b[i]
    if len(b) % 2: out[-1] = b[-1]
    return bytes(out)

def rev(b):
    return b[::-1]

w("【1】三种字节序 × 两个区域 的 8051 顺序解码覆盖率")
w("     （真代码应从 0 一路解到尾，覆盖率 ≈ 1.0）")
w()
for nm, off, size in [("0x00000 真代码", 0x00000, 1024),
                      ("0x19000 官方CFG", 0x19000, 1024),
                      ("0x1E000 起点", 0x1E000, 1024),
                      ("0x1F000 段", 0x1F000, 1024),
                      ("0x1F120 段", 0x1F120, 1024),
                      ("0x04000 白化区", 0x04000, 1024)]:
    b = data[off:off+size]
    w("  —— %s ——" % nm)
    check_seq(b, "原样")
    check_seq(swap16(b), "16 位内字节交换")
    check_seq(b[1:], "从 +1 偏移 (类似反了)")
    check_seq(b[1:][1:], "从 +2 偏移")
    w()

w("【2】0x1E000 前 256 B：三种读法的 8051 反汇编")
def disasm(b, start=0, count=32):
    i = start; out = []
    for _ in range(count):
        if i >= len(b): break
        op = b[i]; step = LEN[op]
        if i + step > len(b): break
        raw = b[i:i+step].hex(" ")
        out.append((i, raw))
        i += step
    return out

for nm, blk in [("原样", data[0x1E000:0x1E000+128]),
                ("字节交换", swap16(data[0x1E000:0x1E000+128]))]:
    w("  【%s】" % nm)
    for off, raw in disasm(blk, 0, 24):
        w("    +0x%02X  %s" % (off, raw))
    w()

w("【3】已知 ARM 片段 0x1F120 的字节交换检验")
blk = data[0x1F120:0x1F120+64]
w("  原样   : %s" % blk.hex(" "))
w("  交换后 : %s" % swap16(blk).hex(" "))
w("  已知原样里含 70 47 (BX LR) 与 bf f3 4f 8f (DMB) ⇒ 说明该子段是 ARM 原生未交换")
w()

w("【4】0x1E000 里的 16 位 u16 前缀带（交换后应成为合法操作码）")
SEG = data[0x1E000:0x20000]
c16 = collections.Counter(int.from_bytes(SEG[i:i+2], "little") for i in range(0, len(SEG)-1, 2))
w("  原样 u16LE Top-16:")
for v, n in c16.most_common(16):
    be = bytes([(v >> 8) & 0xFF, v & 0xFF])
    w("    0x%04X ×%-4d   字节 %s   交换后首字节 0x%02X (=%s)"
      % (v, n, bytes([v & 0xFF, (v >> 8) & 0xFF]).hex(" "), be[0],
         {0x02:"LJMP",0x12:"LCALL",0x22:"RET",0x32:"RETI",0x80:"SJMP",
          0x90:"MOV DPTR,#",0x74:"MOV A,#",0x75:"MOV dir,#",0xE5:"MOV A,dir",
          0xE7:"MOV A,@Ri",0xF7:"MOV @Ri,A",0xFF:"MOV R7,A",0xC2:"CLR bit",
          0x44:"ORL A,#",0x43:"ORL dir,#",0xBD:"CJNE R5",0xAD:"MOV R5,dir",
          0x8D:"MOV dir,R5",0x30:"JNB bit",0x41:"AJMP",0x06:"INC @R0",
          0x08:"INC R0",0x01:"AJMP",0x10:"JBC bit",0x17:"DEC @R1",
          0x98:"SUBB A,R0",0x99:"SUBB A,R1",0xFA:"MOV R2,A",0xF8:"MOV R0,A",
          0x0A:"INC R2",0x20:"JB bit",0x28:"ADD A,R0",0x29:"ADD A,R1",
          0x11:"ACALL",0x40:"JC",0x60:"JZ",0x70:"JNZ",0x50:"JNC",0x80:"SJMP",
          0x04:"INC A",0x05:"INC dir",0x14:"DEC A",0x15:"DEC dir",
          0x24:"ADD A,#",0x25:"ADD A,dir",0x34:"ADDC A,#",0x35:"ADDC A,dir",
          0xA3:"INC DPTR",0xA4:"MUL AB",0xA5:"(reserved)"}.get(be[0], "?")))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
