# -*- coding: utf-8 -*-
"""
round32_haptic_path.py —— 追 0x242B8 的 21 个调用点，尤其 0x1D704-0x1D722 那组

已知（round31）：
  0x24288 / 0x24298 / 0x242A8 = 写 0xAAAA / 0xCCCC / 0x5555 到 0x40003000
  0x242B8(r0, r1) = *(r1+0x14) = r0   ← 单纯的「存字段」函数
  0x1D6F0 函数: 0x242A8 → 0x2418C(r0=u16 data, r1=u8) → 0x24288 → 0x24298
    即完整的「SPI/EEPROM 写一笔」事务序列

本脚本：
  1. 打印 0x1D6F0 完整函数体
  2. 列出 0x242B8 全部 21 个调用点，并解析每个调用点传入的 [r1] 字段偏移
  3. 找出 0x1D6F0 的调用者及其上层
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
        S = (hw1 >> 10) & 1
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
w("round32 —— 追 0x242B8（21 次调用）与 0x1D6F0（SPI 写事务）")
w("=" * 78)
w()

# ============================================================
# 一、0x1D6F0 完整函数体
# ============================================================
w("=" * 78)
w("一、0x1D6F0 —— 「SPI/EEPROM 写一笔」事务函数（完整）")
w("=" * 78)
for x in dis(0x1D6F0, 0x1D740):
    w("   0x%05X  %-10s %s" % (x.address - BASE, x.mnemonic, x.op_str))
w()
w("【判读】")
w("  0x1D6FC  mov.w r0, #0x100        ; 先写 0x100 到某处（可能是使能/标志）")
w("  0x1D700  bl 0x23B58              ; ??")
w("  0x1D704  bl 0x242A8              ; → 写 0x5555 到 0x40003000  (命令: 解锁/写使能)")
w("  0x1D70C  r1 = u8 [sp,#7]         ; 参数 1（函数入参 r0 的低字节）= 命令/类型")
w("  0x1D708  r0 = u16 [sp,#4]        ; 参数 2（函数入参 r1）= 16 位数据")
w("  0x1D710  bl 0x2418C              ; → SPI 命令事务：写 0x5555→等→写 [data]到+8→写 0xAAAA")
w("  0x1D714  bl 0x24288              ; → 写 0xAAAA 到 0x40003000  (命令: 收尾/复位)")
w("  0x1D718  bl 0x24298              ; → 写 0xCCCC 到 0x40003000")
w()

# ============================================================
# 二、0x242B8 的全部调用点
# ============================================================
w("=" * 78)
w("二、0x242B8 的全部调用点 —— 它到底做什么？")
w("=" * 78)
w("0x242B8 反汇编：sub sp,#8 / str r0,[sp,#4] / str r1,[sp] / ldr r0,[sp] / ldr r1,[sp,#4] / str r0,[r1,#0x14] / bx lr")
w("⇒ 语义：  *(r1 + 0x14) = r0     —— 一个「把值存进结构体 +0x14 字段」的 setter")
w()
calls = find_bl_to(0x242B8, 0x242BA)
w("调用点 %d 个：" % len(calls))
for cs, tg in sorted(calls):
    w("   0x%05X" % cs)
w()

w("【逐个调用点的上下文（前 12 条指令）】")
for cs, tg in sorted(calls):
    w("  --- 0x%05X ---" % cs)
    for x in dis(max(0, cs - 34), cs + 6):
        mk = '   <<<<<' if x.address - BASE == cs else ''
        w("     0x%05X  %-10s %-30s%s" % (x.address - BASE, x.mnemonic, x.op_str, mk))
    w()

# ============================================================
# 三、0x1D6F0 的调用者
# ============================================================
w("=" * 78)
w("三、0x1D6F0 的调用者（往上一层）")
w("=" * 78)
c2 = find_bl_to(0x1D6F0, 0x1D6F2)
w("被调用 %d 次：" % len(c2))
for cs, tg in sorted(c2):
    w("   0x%05X" % cs)
w()
for cs, tg in sorted(c2):
    w("  --- 0x%05X 上下文 ---" % cs)
    for x in dis(max(0, cs - 50), cs + 8):
        mk = '   <<<<<' if x.address - BASE == cs else ''
        w("     0x%05X  %-10s %-30s%s" % (x.address - BASE, x.mnemonic, x.op_str, mk))
    w()

# ============================================================
# 四、0x2418C 的调用者
# ============================================================
w("=" * 78)
w("四、0x2418C（SPI 命令事务核心）的调用者")
w("=" * 78)
c3 = find_bl_to(0x2418C, 0x2418E)
for cs, tg in sorted(c3):
    w("   0x%05X" % cs)
w()

# ============================================================
# 五、0x1D6F0 所在的「I2C 状态机」关系（0x1D544 函数）
# ============================================================
w("=" * 78)
w("五、0x1D544 函数（含 I2C1 引用点 0x1D644）—— 看它与 SPI 的关系")
w("=" * 78)
for x in dis(0x1D544, 0x1D6E0):
    fo = x.address - BASE
    mk = ''
    if fo in (0x1D644, 0x1D554, 0x1D57C, 0x1D614): mk = '   <<<<< I2C1/DR/SR1 引用点'
    if fo in (0x1D704, 0x1D710, 0x1D714, 0x1D718): mk = '   <<<<< SPI 调用'
    w("   0x%05X  %-10s %-32s%s" % (fo, x.mnemonic, x.op_str, mk))

open(os.path.join(OUTDIR, 'round32_haptic_path.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L))
