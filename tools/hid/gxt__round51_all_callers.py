#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND51: 修正后的语义 + 剩余全部 caller 的语义
修正1: cmd 0x3200 = 写 0x1B(27) 字节到 flash 偏移 0x1800 (不是单字节)
修正2: cmd 0x1700 -> 0x1AE68 -> 写 0x3800, 长度看 0x1AE68 内部
待定: 0x1AC30 写 0x3800 8 字节 (arg 来自 0x2000403C+0xA)
再查: 0x1B874 全部 9 个 caller 各自写哪个偏移 + 长度
      0x1B7B4 全部 16 个 caller 各自读哪个偏移 + 长度  <== 关键! 能还原完整布局
"""
import os, glob
from capstone import *

g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
D = open(g[0], "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)

def dis(off, n, title="", addrs=None):
    print(f"\n===== {title} @ 0x{off:X} =====")
    for i in md.disasm(D[off:off+n*4], BASE+off):
        mark = ""
        if i.mnemonic in ("bl","blx"):
            try:
                t = int(i.op_str.replace("#",""),16)
                if addrs and t in addrs: mark = "   <== ★"
            except: pass
        print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}{mark}")

FLASHAPI = {0x1B874, 0x1B7B4, 0x1B780, 0x1B82C, 0x1B9C8}

print("="*70)
print("A) 0x1B874 的 9 个 caller —— 各自 addr / len")
print("="*70)
for c in [0x1AC3E, 0x1AC84, 0x1AEF4, 0x1AF0A, 0x1BA90, 0x1EFFC, 0x1F10A, 0x2181E, 0x2190E]:
    # 往回看 0xC 字节找 mov/movs 参数
    lo = max(0x10000, c-0x18)
    print(f"\n--- caller 0x{c:X} (上下文 0x{lo:X}..0x{c+6:X}) ---")
    for i in md.disasm(D[lo:c+6], BASE+lo):
        print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")

print("\n"+"="*70)
print("B) 0x1B7B4 的 16 个 caller —— 各自 off / len  (还原布局)")
print("="*70)
for c in [0x1ABAA, 0x1E5F0, 0x1E670, 0x1E68A, 0x1E6B0, 0x1E6CA, 0x1E6E6, 0x1E6F4,
          0x1F00E, 0x21830, 0x22128, 0x22B3E, 0x22B5C, 0x22BDE, 0x22BFC, 0x232A6]:
    lo = max(0x10000, c-0x14)
    print(f"\n--- caller 0x{c:X} ---")
    for i in md.disasm(D[lo:c+6], BASE+lo):
        print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")
