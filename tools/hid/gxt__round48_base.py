#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND48: 确认 flash 读写库的基址 —— 0x1800 到底是"绝对偏移"还是"相对某段基址"
线索:
  - 0x1BA7C 写 0x1800 -> 调 0x1B874(src, 0x1800, val)
  - 0x1AB90 读 0x1800 -> 0x1B7B4(dst, 0x1800, 0x1B)
  - 0x1B874 内部: cmp r0,#0x7000 ; 然后 add r0, 0x08019000  <-- 那是 src 参数!
  - 关键: r1 (addr=0x1800) 是否也被加基址?
查: 0x1B874 完整反汇编, 看两个参数各自怎么算地址
"""
import os, glob
from capstone import *

FW = None
for c in [r"<WORKSPACE>"]:
    if os.path.exists(c): FW = c
if not FW:
    g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
    FW = g[0]
print("FW =", FW)
D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)

def dis(off, n, title=""):
    print(f"\n===== {title} @ 0x{off:X} =====")
    for i in md.disasm(D[off:off+n*4], BASE+off):
        print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")

# 完整看 0x1B874 (读-改-写包装器)  —— 弄清 addr 参数如何变绝对地址
dis(0x1B874, 50, "0x1B874: flash 读改写包装器 (src, addr, len)")
# 0x1B7B4 读函数
dis(0x1B7B4, 28, "0x1B7B4: flash 读 (dst, off, len)")
# 0x1B780 擦除
dis(0x1B780, 22, "0x1B780: flash 擦页 (page)")

# 找所有 movw #0x1800 / movw #0x7000 / movw #0x9000 movt #0x801 的合法配对
print("\n===== MOVW/MOVT 扫描: 0x08019000 基址引用 =====")
def scan32(D, lo=0x10000, hi=None, step=2):
    if hi is None: hi = len(D)
    sites = []
    for off in range(lo, hi-3, step):
        hw1 = int.from_bytes(D[off:off+2], "little")
        hw2 = int.from_bytes(D[off+2:off+4], "little")
        op = (hw1 >> 5) & 0x1F
        if op != 0x12: continue        # movw
        op2 = (hw2 >> 5) & 0x1F
        if op2 != 0x16: continue       # movt
        def imm16(hw):
            i = ((hw >> 10) & 0x8) | ((hw >> 12) & 0x7) | ((hw >> 1) & 0xF00)
            return i
        rd1 = (hw1 >> 8) & 0xF
        rd2 = (hw2 >> 8) & 0xF
        if rd1 != rd2: continue
        val = (imm16(hw2) << 16) | imm16(hw1)
        sites.append((off, rd1, val))
    return sites

s = scan32(D, 0x10000)
print(f"总 {(len(D)-0x10000)//2} 个半字位, 命中 {len(s)} 个 movw+movt 配对")
targets = {}
for off, rd, val in s:
    targets.setdefault(val, []).append(off)

import collections
cnt = collections.Counter()
for v, offs in targets.items():
    cnt[v] = len(offs)

print("\n--- 高频 imm32 (top 40) ---")
for v, c in cnt.most_common(40):
    print(f"  0x{v:08X}  x{c}")

print("\n--- 0x08019000 基址的所有引用点 ---")
for off in targets.get(0x08019000, []):
    print(f"  file 0x{off:X} (rt 0x{BASE+off:08X})")

print("\n--- 含 0x1800 / 0x3800 / 0x7000 / 0x9000 的所有 imm32 ---")
for v in [0x1800, 0x3800, 0x7000, 0x9000, 0x08019000, 0x08018800, 0x0801A800, 0x0801C800]:
    offs = targets.get(v, [])
    print(f"  0x{v:08X}: {len(offs)} 处 -> " + " ".join(f"{o:X}" for o in offs[:20]))
