# -*- coding: utf-8 -*-
"""
round31_trace2.py —— 用「真调用图」追 0x40003000 / 0x40022000 的调用者

上一版失败原因：函数边界靠 PUSH{...,LR} 启发式，漏掉了 0x24xxx 段。
本版改为**从 BL 目标出发向前反推函数起点**（BL 目标 ± 1 对齐），
并直接打印 0x24xxx 段的反汇编窗口，人工可读。
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

# ---------- 全段扫描：找所有 BL，建调用图 ----------
ALL_BL = []          # (callsite_off, target_off)
for off in range(0x10000, len(D) - 3, 2):
    hw = D[off] | (D[off+1] << 8)
    if (hw >> 11) == 0b11110 and (hw & 0x0F800) in (0x0F800,):   # BL/BLX
        pass
# 用 capstone 线性扫描不可靠，改用「只扫 BL 目标落在 0x24000-0x24600 的调用点」：
def find_bl_to(tlo, thi):
    """找所有 bl 到 [tlo,thi) 区域的调用点（用 word 级线性解码 + BL 编码解析）"""
    res = []
    for off in range(0x10000, len(D) - 3, 2):
        hw1 = D[off] | (D[off+1] << 8)
        hw2 = D[off+2] | (D[off+3] << 8)
        if (hw1 & 0xF800) != 0xF000: continue
        if (hw2 & 0x8000) == 0: continue          # 不是 BL
        S  = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        J1 = (hw2 >> 13) & 1; J2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x7FF
        I1 = (~(J1 ^ S)) & 1; I2 = (~(J2 ^ S)) & 1
        imm = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if imm & (1 << 24): imm -= (1 << 25)
        tgt = off + 4 + imm
        if tlo <= tgt < thi:
            res.append((off, tgt))
    return res

w("=" * 78)
w("round31 —— 追 0x40003000 / 0x40022000 的调用者（第二版：真 BL 解析）")
w("=" * 78)
w()

# ============================================================
# 0x24xxx 段全景（这些是 FLASH/SPI 相关代码的所在地）
# ============================================================
w("=" * 78)
w("零、0x23F00 - 0x24700 全景反汇编（含 FLASH 与 SPI 两个控制器）")
w("=" * 78)
SEG_LO, SEG_HI = 0x23F00, 0x24700
ins = dis(SEG_LO, SEG_HI)
w("共 %d 条, udf %d" % (len(ins), sum(1 for i in ins if i.mnemonic == 'udf')))
w()
SPI_OFF = {0x241A4: 'SPI+0x00 (0x5555 写入点)', 0x241B4: 'SPI+0x0C (状态?)',
           0x241FC: 'SPI+0x04', 0x24212: 'SPI+0x0C (busy轮询)',
           0x2425E: 'SPI+0x08 (16位数据口)', 0x24268: 'SPI+0x00',
           0x24288: 'SPI+0x00 (写 0xAAAA)', 0x24298: 'SPI+0x00 (写 0xCCCC)',
           0x242A8: 'SPI+0x00 (写 0x5555)'}
FLASH_OFF = {0x23F92: 'FLASH+0x00 (ACR)', 0x23FA4: 'FLASH+0x10 (CR, Lock)',
             0x23FD2: 'FLASH+0x10 (CR, ErasePage)', 0x23FE6: 'FLASH+0x14 (AR)',
             0x2407C: 'FLASH+0x0C (SR)', 0x24094: 'FLASH+0x0C (SR)',
             0x240AE: 'FLASH+0x0C (SR)', 0x240C8: 'FLASH+0x0C (SR)',
             0x240F0: 'FLASH+0x10 (Unlock 入口)', 0x24102: 'FLASH+0x04 (KEYR)',
             0x2410A: 'FLASH KEY1 立即数', 0x24146: 'FLASH+0x10 (Program)',
             0x24F9E: 'FLASH+0x00'}
for x in ins:
    fo = x.address - BASE
    mark = ''
    if fo in SPI_OFF: mark = '   <<<<< [SPI] ' + SPI_OFF[fo]
    elif fo in FLASH_OFF: mark = '   <<<<< [FLASH] ' + FLASH_OFF[fo]
    elif fo in PAIRS: mark = '   ; R%d = 0x%08X' % ((D[fo+2] >> 8) & 0xF, PAIRS[fo])
    w("   0x%05X  %-10s %-32s%s" % (fo, x.mnemonic, x.op_str, mark))
w()

# ============================================================
# 一、谁 bl 进 0x242xx（SPI 代码区）
# ============================================================
w("=" * 78)
w("一、谁调用了 SPI 代码区（0x24180 - 0x242C0）")
w("=" * 78)
callers_spi = find_bl_to(0x24180, 0x242C0)
w("找到 %d 个调用点：" % len(callers_spi))
for cs, tg in sorted(callers_spi):
    w("   0x%05X  bl 0x%05X" % (cs, tg))
w()
w("=> 这些调用点附近的反汇编：")
csl = sorted(set(cs for cs, _ in callers_spi))
for lo in csl:
    w("  --- 调用点 0x%05X 上下文 ---" % lo)
    for x in dis(max(0, lo - 40), min(len(D), lo + 24)):
        w("     0x%05X  %-10s %s" % (x.address - BASE, x.mnemonic, x.op_str))
    w()

open(os.path.join(OUTDIR, 'round31_trace2.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L[:60]))
print("... [full output: cfg_parsed/round31_trace2.txt]")
