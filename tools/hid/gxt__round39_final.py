# -*- coding: utf-8 -*-
"""
round39_final.py —— 最终收口：0x1B6E0 / 0x1B7B4 / 0x1B874 三个封装函数的语义

round38 发现 0x1B6C0-0x1BA24 区间被调用 33 次，其中有 3 个不同入口：
   0x1B6E0  (被 3 次调用)
   0x1B7B4  (被 21 次调用)
   0x1B874  (被 ? 次调用)   ← 含 FLASH_Unlock/Lock + 擦/写

本脚本给出三者完整函数体 + 各自调用者分类，形成最终结论。
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
w("round39 —— 最终收口：0x1B6E0 / 0x1B7B4 / 0x1B874 三者语义")
w("=" * 78)
w()

for start, end, nm in ((0x1B6E0, 0x1B780, '0x1B6E0'), (0x1B7B4, 0x1B874, '0x1B7B4'),
                       (0x1B874, 0x1BA24, '0x1B874')):
    cc = find_bl_to(start, start + 2)
    w("=" * 78)
    w("%s  被调用 %d 次" % (nm, len(cc)))
    w("   调用点: %s" % ', '.join('0x%05X' % cs for cs, _ in sorted(cc)))
    w("=" * 78)
    for x in dis(start, end):
        fo = x.address - BASE
        mk = ''
        if fo in (0x1B790, 0x1B7AA, 0x1B8FC, 0x1B944, 0x1B9E0, 0x1BA1A): mk = '   <<<<< 关键'
        if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
            mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
        w("   0x%05X  %-10s %-34s%s" % (fo, x.mnemonic, x.op_str, mk))
    w()

# ---------- 0x1B6E0 的调用者分类 ----------
w("=" * 78)
w("附：0x1B6E0 的 3 个调用者上下文")
w("=" * 78)
for cs, tg in sorted(find_bl_to(0x1B6E0, 0x1B6E2)):
    w("  --- 0x%05X ---" % cs)
    for x in dis(max(0, cs - 46), cs + 8):
        mk = '   <<<<<' if x.address - BASE == cs else ''
        w("     0x%05X  %-10s %-30s%s" % (x.address - BASE, x.mnemonic, x.op_str, mk))
    w()

open(os.path.join(OUTDIR, 'round39_final.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L))
