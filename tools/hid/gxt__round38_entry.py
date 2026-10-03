# -*- coding: utf-8 -*-
"""
round38_entry.py —— 找固件写入的最终入口（命令分派）

已知链（round36/37）：
  固件写入二级封装：
     0x1B780  = 擦一页 (Unlock → CR|=2(PER) → AR=param<<10 → CR|=0x40 → 等 → Lock)
     0x1B9C8  = 写 1KB (Unlock → 循环{r1=[buf]; bl 0x24124}=(PG + halfword write) → Lock)
     0x1BCA0  = 写 4 字节 (Unlock → bl 0x24124 → Lock)
     被 0x1B8FC / 0x1B944 调用 ← 同一个大函数（帧缓冲 0x400+ 字节）

本脚本：找 0x1B780 所在的大函数的入口，以及它被谁调用（命令分派器）
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
w("round38 —— 找固件写入的入口（自顶向下）")
w("=" * 78)
w()

# 大函数起点：0x1B780 与 0x1B944 所属应该是同一个函数。找它的入口。
w("=" * 78)
w("一、写入函数所属的大函数（从 0x1B8FC / 0x1B944 向前找 PUSH 起点）")
w("=" * 78)
for probe in (0x1B780, 0x1B8FC, 0x1B944, 0x1B9C8):
    w("  探针 0x%05X:" % probe)
    # 向前扫描找 PUSH {...} 且后面跟着大 sp 调整
    for off in range(probe, max(0x1B000, probe - 0x600), -2):
        hw = D[off] | (D[off+1] << 8)
        if hw == 0xB580 or (0xB400 <= hw <= 0xB5FF):   # push {r7,lr} 家族
            # 看接下来几字节是不是大栈帧
            nxt = D[off+2:off+8]
            w("    疑似起点 0x%05X  hw=0x%04X  后续 %s" % (off, hw, nxt.hex(' ')))
            break
w()

# ---------- 关键：谁调用这个大函数 ----------
w("=" * 78)
w("二、0x1B780 所在大函数的全部调用者")
w("=" * 78)
# 大函数范围：假设从 0x1B6xx 到 0x1BA30（0x1BA22 movs r0,r0 之后 0x1BA24 是新函数）
FSTART, FEND = 0x1B6C0, 0x1BA24
cc = find_bl_to(FSTART, FEND)
w("  区间 0x%05X-0x%05X 被调用 %d 次:" % (FSTART, FEND, len(cc)))
for cs, tg in sorted(cc):
    w("     0x%05X  bl 0x%05X" % (cs, tg))
w()
for cs, tg in sorted(cc):
    w("  --- 调用者上下文 0x%05X (→0x%05X) ---" % (cs, tg))
    for x in dis(max(0, cs - 70), cs + 12):
        mk = '   <<<<<' if x.address - BASE == cs else ''
        if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
            mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
        w("     0x%05X  %-10s %-32s%s" % (x.address - BASE, x.mnemonic, x.op_str, mk))
    w()

# ---------- 0x1B700-0x1B980 全景（看这个函数的参数与结构） ----------
w("=" * 78)
w("三、0x1B6C0 - 0x1B980 全景（写入函数前半，看它的参数）")
w("=" * 78)
for x in dis(0x1B6C0, 0x1B980):
    fo = x.address - BASE
    mk = ''
    if fo in (0x1B790, 0x1B7AA, 0x1B8FC, 0x1B944): mk = '   <<<<< 关键点'
    if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
        mk += '  → 0x%05X' % (x.operands[0].imm & ~1)
    w("   0x%05X  %-10s %-34s%s" % (fo, x.mnemonic, x.op_str, mk))

open(os.path.join(OUTDIR, 'round38_entry.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L[:130]))
