# -*- coding: utf-8 -*-
"""
round37_write_path.py —— 确认真正的固件写入路径

round36 发现：
  区域 A @0x1B780: FLASH_Unlock → 0x3F80(0x307) → 0x3FB8(param<<10) → 0x3F80(0x307) → FLASH_Lock
  区域 B @0x1B9C8: FLASH_Unlock → 循环{ r1=[buf]; bl 0x24124 } → 0x3F80(0x307) → FLASH_Lock
  区域 C @0x1BC60: 待看

关键未知：0x24124 是什么？（在半字写循环里被调用）
          0x23FB8 是什么？（区域 A 里传 param<<10）

本脚本：
 1. 0x24100-0x24180 全景（0x24124 / 0x24146 FLASH_Program 的关系）
 2. 0x23FB8 完整
 3. 区域 C 全景
 4. 0x1B780 / 0x1B9C8 各自的调用者（升级入口）
"""
import os
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
w("round37 —— 确认真实固件写入路径")
w("=" * 78)
w()

# ---------- 1. 0x24100 - 0x24180 全景 ----------
w("=" * 78)
w("一、0x24100 - 0x24180 全景（0x24124 是什么？）")
w("=" * 78)
for x in dis(0x24100, 0x24180):
    fo = x.address - BASE
    mk = ''
    if fo in (0x2410A, 0x24124, 0x24146): mk = '   <<<<< 关注点'
    if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
        mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
    w("   0x%05X  %-10s %-34s%s" % (fo, x.mnemonic, x.op_str, mk))
w()

# ---------- 2. 0x23FB8 完整 ----------
w("=" * 78)
w("二、0x23FB8 完整函数体（区域 A 调用：0x3FB8(param<<10)）")
w("=" * 78)
for x in dis(0x23FB8, 0x23FD2):
    fo = x.address - BASE
    mk = ''
    if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
        mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
    w("   0x%05X  %-10s %-34s%s" % (fo, x.mnemonic, x.op_str, mk))
w()

# ---------- 3. 区域 C ----------
w("=" * 78)
w("三、区域 C：0x1BC60 - 0x1BD00")
w("=" * 78)
for x in dis(0x1BC60, 0x1BD00):
    fo = x.address - BASE
    mk = ''
    if fo in (0x1BCA8, 0x1BCBC): mk = '   <<<<< FLASH Unlock/Lock'
    if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
        mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
    w("   0x%05X  %-10s %-34s%s" % (fo, x.mnemonic, x.op_str, mk))
w()

# ---------- 4. 0x1B780 / 0x1B9C8 的调用者 ----------
w("=" * 78)
w("四、0x1B780 / 0x1B9C8 的调用者（升级入口）")
w("=" * 78)
for t, nm in ((0x1B780, '0x1B780 (区域A: 整块擦+写)'), (0x1B9C8, '0x1B9C8 (区域B: 半字写循环)')):
    cc = find_bl_to(t, t + 2)
    w("  %s 被调用 %d 次: %s" % (nm, len(cc), ', '.join('0x%05X' % cs for cs, _ in sorted(cc)) or '(无)'))
    for cs, _ in sorted(cc):
        w("    --- 调用者上下文 0x%05X ---" % cs)
        for x in dis(max(0, cs - 40), cs + 10):
            mk = '   <<<<<' if x.address - BASE == cs else ''
            if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
                mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
            w("       0x%05X  %-10s %-30s%s" % (x.address - BASE, x.mnemonic, x.op_str, mk))
    w()

open(os.path.join(OUTDIR, 'round37_write_path.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L))
