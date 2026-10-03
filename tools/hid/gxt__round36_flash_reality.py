# -*- coding: utf-8 -*-
"""
round36_flash_reality.py —— FLASH_Unlock/Lock 的 4 组真实调用点解剖

核心反转：
  FLASH_ErasePage (0x23FD2) 被调用 0 次  ← 死代码
  FLASH_Program  (0x24146) 被调用 0 次  ← 死代码
  但 FLASH_Unlock (0x240F0) 有 4 个真实调用点：0x1B790, 0x1B9E0, 0x1BCA8, 0x23F5E
      FLASH_Lock   (0x23FA4) 有 4 个真实调用点：0x1B7AA, 0x1BA1A, 0x1BCBC, 0x23F78

本脚本：解剖 0x1B790 / 0x1B9E0 / 0x1BCA8 三处（0x23F5E/0x23F78 是 0x23F58 那个包装函数）
看这些 Unlock..Lock 区间里到底写了什么。
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

NOTE = {0x1B790: 'FLASH_Unlock 调用点', 0x1B7AA: 'FLASH_Lock 调用点',
        0x1B9E0: 'FLASH_Unlock 调用点', 0x1BA1A: 'FLASH_Lock 调用点',
        0x1BCA8: 'FLASH_Unlock 调用点', 0x1BCBC: 'FLASH_Lock 调用点'}

w("=" * 78)
w("round36 —— FLASH_Unlock/Lock 的 3 组真实调用点解剖")
w("=" * 78)
w()
w("★ 核心反转（round35）：ErasePage(0x23FD2) 与 Program(0x24146) 被调用 **0 次** ⇒ 死代码。")
w("   但 Unlock(0x240F0) / Lock(0x23FA4) 各有 4 个真实调用点。")
w("   本脚本看 Unlock..Lock 区间内到底写了什么。")
w()

# 三个区域
REGIONS = [(0x1B700, 0x1B7E0, 'A'), (0x1B980, 0x1BA60, 'B'), (0x1BC60, 0x1BD00, 'C')]
for lo, hi, tag in REGIONS:
    w("=" * 78)
    w("区域 %s：0x%05X - 0x%05X" % (tag, lo, hi))
    w("=" * 78)
    for x in dis(lo, hi):
        fo = x.address - BASE
        mk = ''
        if fo in NOTE: mk = '   <<<<< ' + NOTE[fo]
        if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
            mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
        w("   0x%05X  %-10s %-34s%s" % (fo, x.mnemonic, x.op_str, mk))
    w()

# ---------- 这三个 Unlock 调用点的上层 ----------
w("=" * 78)
w("三、谁调用包含这些 Unlock 的函数")
w("=" * 78)
for probe in (0x1B700, 0x1B980, 0x1BC60):
    cc = find_bl_to(probe, probe + 0x100)
    w("  区间 0x%05X 被调用: %s" % (probe, ', '.join('0x%05X→0x%05X' % (cs, tg) for cs, tg in sorted(cc)) or '(无)'))
w()

# ---------- 0x23F58 包装函数的上层 ----------
w("=" * 78)
w("四、0x23F58（含 Unlock+Lock 的包装函数）被谁调用")
w("=" * 78)
cc = find_bl_to(0x23F58, 0x23F5A)
w("  被调用 %d 次: %s" % (len(cc), ', '.join('0x%05X' % cs for cs, _ in sorted(cc)) or '(无)'))
for cs, tg in sorted(cc):
    w("  --- 0x%05X 上下文 ---" % cs)
    for x in dis(max(0, cs - 60), cs + 12):
        mk = '   <<<<<' if x.address - BASE == cs else ''
        if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
            mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
        w("     0x%05X  %-10s %-32s%s" % (x.address - BASE, x.mnemonic, x.op_str, mk))
    w()

open(os.path.join(OUTDIR, 'round36_flash_reality.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L))
