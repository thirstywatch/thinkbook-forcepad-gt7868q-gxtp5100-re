# -*- coding: utf-8 -*-
"""
round33_upper.py —— 追 0x229FA（唯一的 SPI 写事务调用者）向上

已知链：
  0x1D6F0(cmd, u16data)  = SPI/EEPROM 写一笔事务
      ↓ 调用者 0x229FA   ← 本脚本重点
  0x1D6F0 → 0x242A8(0x5555) → 0x2418C(data,cmd) → 0x24288(0xAAAA) → 0x24298(0xCCCC)
  0x2418C 只被 0x1D710 调用 ⇒ 这条 SPI 通路是专用的

本脚本：
  1. 0x229FA 所在函数的完整反汇编
  2. 该函数被谁调用（再上一层）
  3. 该函数内的所有地址常量（可能指向 SRAM 缓冲 / 波形数据）
  4. 附近 0x22900-0x22B00 全景
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

def dec_mov(off):
    if off + 4 > len(D): return None
    hw1 = D[off] | (D[off+1] << 8); hw2 = D[off+2] | (D[off+3] << 8)
    if (hw1 >> 11) != 0b11110: return None
    op = hw1 & 0x0FF0
    if op not in (0x240, 0x2C0): return None
    imm4 = hw1 & 0xF; i = (hw1 >> 10) & 1; imm3 = (hw2 >> 12) & 7
    return ('MOVW' if op == 0x240 else 'MOVT'), (hw2 >> 8) & 0xF, \
           (imm4 << 12) | (i << 11) | (imm3 << 8) | (hw2 & 0xFF)

mw = {}; mt = {}
for off in range(0x10000 & ~1, len(D) - 3, 2):
    r = dec_mov(off)
    if not r: continue
    k, rd, imm = r
    (mw if k == 'MOVW' else mt)[off] = (rd, imm)
PAIRS = {}
for o1, (r1, i1) in mw.items():
    for d in (2, 4, 6, 8, 10, 12, 14, 16):
        o2 = o1 + d
        if o2 in mt and mt[o2][0] == r1:
            PAIRS[o1] = ((mt[o2][1] << 16) | i1); break

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
w("round33 —— 追 0x229FA（SPI 写事务唯一调用者）")
w("=" * 78)
w()

# ============================================================
# 一、0x22900 - 0x22B80 全景
# ============================================================
w("=" * 78)
w("一、0x22900 - 0x22B80 全景反汇编")
w("=" * 78)
for x in dis(0x22900, 0x22B80):
    fo = x.address - BASE
    mk = ''
    if fo in PAIRS: mk = '   ; R%d = 0x%08X' % ((D[fo+2] >> 8) & 0xF, PAIRS[fo])
    if fo == 0x229FA: mk = '   <<<<< 调用 SPI 写事务 0x1D6F0'
    w("   0x%05X  %-10s %-32s%s" % (fo, x.mnemonic, x.op_str, mk))
w()

# ============================================================
# 二、谁调用 0x229xx 这一段
# ============================================================
w("=" * 78)
w("二、谁调用 0x22900-0x22B80 区间（含 0x229FA）")
w("=" * 78)
cc = find_bl_to(0x22900, 0x22B80)
for cs, tg in sorted(cc):
    w("   0x%05X  bl 0x%05X" % (cs, tg))
w()
if cc:
    w("=> 调用点上下文：")
    for cs, tg in sorted(set(cc)):
        w("  --- 0x%05X (→0x%05X) ---" % (cs, tg))
        for x in dis(max(0, cs - 40), cs + 8):
            mk = '   <<<<<' if x.address - BASE == cs else ''
            w("     0x%05X  %-10s %-30s%s" % (x.address - BASE, x.mnemonic, x.op_str, mk))
        w()

# ============================================================
# 三、0x229xx 段内的 SRAM / 地址常量
# ============================================================
w("=" * 78)
w("三、0x22900-0x22B80 段内的 MOVW/MOVT 常量（指向 SRAM 或数据区）")
w("=" * 78)
for o, a in sorted(PAIRS.items()):
    if 0x22900 <= o < 0x22B80:
        tag = ''
        if 0x20000000 <= a < 0x20010000: tag = '  ← SRAM'
        elif 0x08000000 <= a < BASE + len(D): tag = '  ← Flash(文件内 0x%05X)' % (a - BASE)
        elif a > 0x40000000: tag = '  ← 外设'
        w("   0x%05X  = 0x%08X%s" % (o, a, tag))

open(os.path.join(OUTDIR, 'round33_upper.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L[:200]))
