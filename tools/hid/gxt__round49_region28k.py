#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND49: 决定性判据 —— 0x1800 落点是不是"必须可读的结构化数据"?
逻辑:
  0x1AB90 是主机命令 0x1B 的 handler:
     读 flash 0x1800 起 0x1B (27) 字节 -> 通过 0x22728 作为 report 0x1C 回给主机
  这个 handler 的行为 = "把 27 字节原样回传"
  => 这 27 字节必然是一个有意义的"配置块"或"标识块"
  => 如果它落在代码上, 那说明基址判断错了

关键待验事项:
  A) 0x08019000+0x1800 = 0x0801A800, file 0x1A800 -> 反汇编 = 代码?  (已看, 像代码)
  B) 但是! 0x1B874 包装器里的 cmp #0x7000 是在 add 之前 -> 0x7000 是 off 上限
     => 可访问范围 = 0x08019000 .. 0x0801FFFF, 共 0x7000 = 28 KB
     => 这个 28 KB 是一个独立的"数据区", 在第 2 段(明文区)开头!
  C) 那 0x08019000 本身是什么? 如果 28 KB 区域是数据区, 那 0x08019000 起始处
     应该是数据而不是代码.
  => 决定性检验: 把 0x08019000..0x0801FFFF (28 KB) 单独拿出来做熵分析 + 结构分析
     看它是不是"参数区"而不是"代码区"
  D) 还要看: 有没有别的路径读这个区域(不只是 0x1800), 从而恢复出完整布局
"""
import os, glob, math, collections
from capstone import *

FW = None
g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
if g: FW = g[0]
print("FW =", FW)
D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)

def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

# ── A. 28 KB 数据区: file 0x19000 .. 0x1FFFF ──
print("\n=== 28KB 区 (file 0x19000..0x1FFFF) 逐 1KB 熵 ===")
print("  (0x1B7B4 的 cmp #0x7000 允许 off 0..0x6FFF => 绝对 0x08019000..0x0801FFFF)")
tot_hi = 0
for p in range(0x19000, 0x20000, 0x400):
    e = ent(D[p:p+0x400])
    bar = "#" * int(e*8)
    tag = ""
    if e > 7.5: tag = "  <== 高熵"
    print(f"  0x{p:05X}  {e:5.3f}  {bar}{tag}")
    if e > 7.5: tot_hi += 1
print(f"\n高熵页数 = {tot_hi} / {len(range(0x19000,0x20000,0x400))}")

# ── B. 0x08019000 起始处反汇编 ──
print("\n=== 0x08019000 (file 0x19000) 反汇编 ===")
for i in md.disasm(D[0x19000:0x19000+0x80], BASE+0x19000):
    print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")

# ── C. 0x0801A800 (=0x19000+0x1800) 附近, 看是否有明显数据表 ──
print("\n=== file 0x1A7F0..0x1A900 hexdump (0x1800 落点前后) ===")
for r in range(0x1A7F0, 0x1A900, 16):
    ch = D[r:r+16]
    print(f"  {r:06X}  " + " ".join(f"{b:02X}" for b in ch) + "  " +
          "".join(chr(b) if 32<=b<127 else "." for b in ch))

# ── D. 深挖: 0x1AB90 handler 的调用者 & 0x3200 的 caller, 看谁触发 ──
def find_bl(D, tgt, lo=0x10000, hi=None, step=2):
    if hi is None: hi = len(D)-3
    out = []
    for off in range(lo, hi, step):
        hw1 = int.from_bytes(D[off:off+2], "little")
        hw2 = int.from_bytes(D[off+2:off+4], "little")
        if (hw1 & 0xF800) == 0xF000 and (hw2 & 0xD000) == 0xD000:
            s = (hw1 >> 10) & 1
            j1 = (hw2 >> 13) & 1; j2 = (hw2 >> 11) & 1
            i1 = (~(s ^ j1)) & 1; i2 = (~(s ^ j2)) & 1
            i10 = hw1 & 0x3FF; i11 = hw2 & 0x7FF
            imm = (s << 24) | (i1 << 23) | (i2 << 22) | (i10 << 12) | (i11 << 1)
            if imm & 0x1000000: imm -= 0x2000000
            pc = off + 4 + imm
            if pc == tgt: out.append(off)
    return out

print("\n=== 调用者追踪 ===")
for name, t in [("0x1AB90 cmd0x1B读0x1800", 0x1AB90),
                ("0x1BA7C 写0x1800单字节", 0x1BA7C),
                ("0x1AC30 写0x3800(8B)", 0x1AC30),
                ("0x1AE68 cmd0x1700写0x3800", 0x1AE68),
                ("0x1B874 flash读写包装器", 0x1B874),
                ("0x1B7B4 flash读", 0x1B7B4)]:
    c = find_bl(D, t)
    print(f"  {name}: {len(c)} 个 caller -> " + " ".join(f"0x{o:X}" for o in c))
