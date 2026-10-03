# -*- coding: utf-8 -*-
"""
★★ 重大发现：固件尾部 0x19A00-0x2775C 存在 ~56 KB 明文（我此前误判为"容器尾"）
本脚本：
 1. 精确定位明文/白化边界
 2. 提取所有 ASCII 串（找版本号、函数名、错误信息）
 3. 0x19A00 处（rel 0.966 全固件最强）反汇编
 4. 明文段的整体结构
"""
import os, collections, re

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "tail_plaintext.txt")
data = open(FW, "rb").read()
L = len(data)
lines = []
def w(s=""):
    lines.append(s); print(s)

RELOPS = set((0x80,0x70,0x60,0x50,0x40,0x30,0x20,0x10,
              0x01,0x21,0x41,0x61,0x81,0xa1,0xc1,0xe1,
              0x11,0x31,0x51,0x71,0x91,0xb1,0xd1,0xf1))
def relscore(b):
    n = 0; ok = 0
    for i in range(len(b)-1):
        if b[i] in RELOPS:
            rel = b[i+1] - 256 if b[i+1] >= 128 else b[i+1]
            n += 1
            if abs(rel) <= 8: ok += 1
    return (ok/n if n >= 6 else None)

def H(b):
    import math
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())

w("=" * 84)
w("固件尾部明文区挖掘")
w("=" * 84); w()

w("【1】细粒度边界定位（256 B 窗口，步长 128 B，0x19800 - 0x27800）")
w("  偏移       rel    熵     零%   判定")
for o in range(0x19800, min(L-256, 0x27800), 128):
    win = data[o:o+256]
    sc = relscore(win)
    v = "?" if sc is None else ("★代码" if sc >= 0.35 else ("混合" if sc >= 0.20 else "白化"))
    w("  0x%05X  %s  %.3f  %4.1f  %s"
      % (o, ("%.3f" % sc) if sc else " --  ", H(win), win.count(0)/256*100, v))
w()

w("【2】全固件 ASCII 串提取（>=6 字符），按偏移列出")
runs = []
cur = b""; start = 0
for i, b_ in enumerate(data):
    if 0x20 <= b_ < 0x7f:
        if not cur: start = i
        cur += bytes([b_])
    else:
        if len(cur) >= 6: runs.append((start, cur))
        cur = b""
if len(cur) >= 6: runs.append((start, cur))
w("  共 %d 条（>=6 字符）:" % len(runs))
for off, s in runs:
    tag = "明文区" if relscore(data[max(0,off-64):off+len(s)+64]) and (relscore(data[max(0,off-64):off+len(s)+64]) or 0) >= 0.2 else "白化区"
    w("  0x%05X  [%-8s]  %s" % (off, tag, s.decode("ascii", "replace")))
w()

w("【3】0x19A00（rel 0.966，全固件最强代码信号）反汇编")
LEN8051 = {}
for x in (0x00,0x03,0x04,0x05,0x13,0x14,0x15,0x23,0x24,0x25,0x33,0x34,0x35,
          0x43,0x44,0x45,0x53,0x54,0x55,0x63,0x64,0x65,0x73,0x74,0x75,
          0x83,0x84,0x85,0x93,0x94,0x95,0xA3,0xA4,0xA5,0xB3,0xB4,0xB5,
          0xC3,0xC4,0xC5,0xD3,0xD4,0xD5,0xE3,0xE4,0xE5,0xF3,0xF4,0xF5,
          0x02,0x12): LEN8051[x] = 3 if x in (0x02,0x12) else 2
for x in (0x01,0x21,0x41,0x61,0x81,0xA1,0xC1,0xE1,0x11,0x31,0x51,0x71,0x91,0xB1,0xD1,0xF1,
          0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80,0x90,0xA0,0xB0,0xC0,0xD0,0xE0,0xF0):
    LEN8051[x] = 2
for x in range(256): LEN8051.setdefault(x, 1)

NAMES = {0x02:"LJMP",0x12:"LCALL",0x22:"RET",0x32:"RETI",0x80:"SJMP",0x90:"MOV DPTR,#",
         0x74:"MOV A,#",0x75:"MOV dir,#",0xE5:"MOV A,dir",0xE7:"MOV A,@R1",0xF7:"MOV @R1,A",
         0x43:"ORL dir,#",0x53:"ANL dir,#",0xC2:"CLR bit",0xD2:"SETB bit",0xC0:"PUSH",
         0xD0:"POP",0x00:"NOP",0x05:"INC dir",0x85:"MOV dir,dir",0x44:"ORL A,#",0x54:"ANL A,#",
         0x24:"ADD A,#",0x34:"ADDC A,#",0x94:"SUBB A,#",0x04:"INC A",0x14:"DEC A",
         0xBD:"CJNE R5,#",0xAD:"MOV R5,dir",0x8D:"MOV dir,R5",0x30:"JNB bit",0x40:"JC",
         0x20:"JB",0x70:"JNZ",0x60:"JZ",0x50:"JNC",0x10:"JBC",0xA3:"INC DPTR",0xA4:"MUL AB",
         0x7F:"MOV R7,#",0x7E:"MOV R6,#",0x78:"MOV R0,#",0x79:"MOV R1,#",0xE0:"MOVX A,@DPTR",
         0xF0:"MOVX @DPTR,A",0x93:"MOVC A,@A+DPTR",0x83:"MOVC A,@A+PC",0x03:"RR A",
         0x13:"RRC A",0x23:"RL A",0x33:"RLC A",0xC3:"CLR C",0xD3:"SETB C",0xEE:"MOV A,R6",
         0xEF:"MOV A,R7",0xFE:"MOV R6,A",0xFF:"MOV R7,A"}

def disasm(b, base, count=48):
    out = []; i = 0
    for _ in range(count):
        if i >= len(b): break
        op = b[i]; step = LEN8051[op]
        if i + step > len(b): break
        raw = b[i:i+step]
        out.append((base+i, raw, NAMES.get(op, "?")))
        i += step
    return out

for base in (0x19A00, 0x1A000, 0x20000, 0x26C00, 0x26E00):
    w("  —— 0x%05X ——" % base)
    for off, raw, nm in disasm(data[base:base+256], base, 24):
        w("    0x%05X  %-12s %s" % (off, raw.hex(" "), nm))
    w()

w("【4】0x19A00 区（0x19A00-0x1A000, 1536 B）整体统计")
seg = data[0x19A00:0x1A000]
w("  熵 %.3f  零占比 %.3f  rel %.3f" % (H(seg), seg.count(0)/len(seg), relscore(seg) or 0))
w("  最高频: %s" % ", ".join("0x%02X:%d" % (b, n) for b, n in collections.Counter(seg).most_common(10)))
w()

w("【5】尾部明文区的段划分（按 rel 与熵）")
segs = []
cur = None
for o in range(0x19000, L-256, 256):
    sc = relscore(data[o:o+256])
    if sc is None: continue
    kind = "代码" if sc >= 0.30 else ("混合" if sc >= 0.18 else "白化")
    if cur and cur[2] == kind and o - cur[1] <= 256:
        cur = (cur[0], o, kind, max(cur[3], sc))
    else:
        if cur: segs.append(cur)
        cur = (o, o, kind, sc)
if cur: segs.append(cur)
w("  区间划分（>1 KB 才列）:")
for a, b, k, mx in segs:
    if b - a >= 1024:
        w("    0x%05X – 0x%05X  (%6d B)  %-4s  峰值 rel %.3f" % (a, b+256, b+256-a, k, mx))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
