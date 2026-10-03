# -*- coding: utf-8 -*-
"""
round35_flash_caller.py —— 追片上 FLASH 驱动 (0x40022000) 的调用者

FLASH 驱动五函数（round21 已解出）：
   FLASH_Lock       0x23FA4
   FLASH_Unlock     0x240F0
   FLASH_ErasePage  0x23FD2
   FLASH_Program    0x24146
   FLASH_WaitBusy   0x24074

本脚本追每个函数的调用者，向上逐层，找「固件是怎么被写进去的」的入口。
另外：交叉验证 0x40003000 的性质 —— 它是否真的是 SPI。
"""
import os
from collections import Counter, defaultdict
from capstone import *
from capstone.arm import *

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(FW, 'rb').read()
BASE = 0x08000000
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed')
L = []
def w(s=''):
    L.append(str(s))

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = True

def dis(lo, hi):
    return list(md.disasm(D[lo:hi], BASE + lo))

def find_bl_to(tlo, thi, scan_lo=0x10000, scan_hi=None):
    if scan_hi is None: scan_hi = len(D)
    res = []
    for off in range(scan_lo, scan_hi - 3, 2):
        hw1 = D[off] | (D[off+1] << 8)
        hw2 = D[off+2] | (D[off+3] << 8)
        if (hw1 & 0xF800) != 0xF000: continue
        if (hw2 & 0x8000) == 0: continue
        S = (hw1 >> 10) & 1; imm10 = hw1 & 0x3FF
        J1 = (hw2 >> 13) & 1; J2 = (hw2 >> 11) & 1; imm11 = hw2 & 0x7FF
        I1 = (~(J1 ^ S)) & 1; I2 = (~(J2 ^ S)) & 1
        imm = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if imm & (1 << 24): imm -= (1 << 25)
        tgt = off + 4 + imm
        if tlo <= tgt < thi: res.append((off, tgt))
    return res

w("=" * 78)
w("round35 —— 追片上 FLASH 驱动 (0x40022000) 的调用者")
w("=" * 78)
w()

FLASHF = {
    'FLASH_Lock':      0x23FA4,
    'FLASH_ErasePage': 0x23FD2,
    'FLASH_WaitBusy':  0x24074,
    'FLASH_Unlock':    0x240F0,
    'FLASH_Program':   0x24146,
}

for nm, addr in FLASHF.items():
    cc = find_bl_to(addr, addr + 2)
    w("%s (0x%05X) 被调用 %d 次: %s" % (nm, addr, len(cc),
      ', '.join('0x%05X' % cs for cs, _ in sorted(cc)) or '(无直接 bl)'))
w()

# ---------- 1. ErasePage / Program 的调用者（最关键） ----------
for nm in ('FLASH_ErasePage', 'FLASH_Program'):
    addr = FLASHF[nm]
    w("=" * 78)
    w("一、%s (0x%05X) 的调用点上下文 —— 「谁在擦/写 flash」" % (nm, addr))
    w("=" * 78)
    for cs, tg in sorted(find_bl_to(addr, addr + 2)):
        w("  --- 调用点 0x%05X ---" % cs)
        for x in dis(max(0, cs - 90), cs + 20):
            fo = x.address - BASE
            mk = '   <<<<<' if fo == cs else ''
            if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
                mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
            w("     0x%05X  %-10s %-32s%s" % (fo, x.mnemonic, x.op_str, mk))
        w()

# ---------- 2. 0x23F30-0x24180 全景（FLASH 驱动本体 + 上层） ----------
w("=" * 78)
w("二、0x23F30 - 0x24180 全景（FLASH 驱动与它的上层函数）")
w("=" * 78)
for x in dis(0x23F30, 0x24180):
    fo = x.address - BASE
    FLASH_KEY = {0x23F92:'FLASH+0x00 ACR', 0x23FA4:'FLASH_Lock 入口 CR|=0x80',
                 0x23FB8:'?', 0x23FD2:'FLASH_ErasePage 入口', 0x23FE6:'FLASH_AR',
                 0x24074:'FLASH_WaitBusy 入口', 0x240F0:'FLASH_Unlock 入口',
                 0x24102:'FLASH_KEYR', 0x2410A:'KEY1 movw', 0x24146:'FLASH_Program 入口'}
    mk = ''
    if fo in FLASH_KEY: mk = '   <<<<< ' + FLASH_KEY[fo]
    if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
        mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
    w("   0x%05X  %-10s %-32s%s" % (fo, x.mnemonic, x.op_str, mk))
w()

open(os.path.join(OUTDIR, 'round35_flash_caller.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L[:100]))
