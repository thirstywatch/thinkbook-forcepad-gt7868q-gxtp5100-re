#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND55: 看 0x1B82C(读页) / 0x1B9C8(写页) 内部 —— 真正的物理访问在哪
假设: 0x08019000+off 只是"逻辑地址", 后面一定会被换算成
      ① SPI/EEPROM 命令  或  ② 真实的 flash 控制器操作
如果 0x1B82C 内部只是 memcpy(从 0x08019000+page*0x400), 那它就是
   "从 flash 的某个区读" —— 而那区是代码 => 矛盾
如果内部有 SPI/外设操作 => 目标其实是外部 EEPROM

★ 决定性: 看 0x1B82C 内部
"""
import os, glob
from capstone import *

g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
D = open(g[0], "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB+CS_MODE_MCLASS)

def dis(off, n, title):
    print(f"\n===== {title} @ 0x{off:X} =====")
    for i in md.disasm(D[off:off+n], BASE+off):
        print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")

dis(0x1B82C, 0x80, "0x1B82C: 读页 (dst, page)")
dis(0x1B9C8, 0x70, "0x1B9C8: 写页 (buf, addr, len)")
dis(0x240F0, 0x40, "0x240F0: FLASH_Unlock? (被 0x1B780 调用)")
dis(0x23F80, 0x40, "0x23F80: (被 0x1B780 调用)")
dis(0x23FB8, 0x50, "0x23FB8: 内联 Erase")
dis(0x23FA4, 0x20, "0x23FA4")
