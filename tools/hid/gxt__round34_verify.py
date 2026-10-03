# -*- coding: utf-8 -*-
"""
round34_verify.py —— 交叉验证两条通路的真实性质

【假设 A】0x229D0 的 0x229FA 分支 = 出厂自检「写测试字 → 读回比对」
   证据：0x229E8 立即数 0xA55A（= 0x5AA5 位反转，典型 OTP/EEPROM 测试字）
         0x229F4 movs r0,#2 ; movw r1,#0xF9F  ⇒ 写 (cmd=2, data=0x0F9F)
         0x22A00 立即返回，无读回 ⇒ 需要找 0x229D0 的调用者看它是否比对

【假设 B】0x24820 附近 = 固件升级序列
   0x24820 bl 0x1AF70 / 0x24824 bl 0x20838 / 0x24828 bl 0x229D0 / 0x2482C bl 0x22A04

本脚本：
 1. 0x229D0 / 0x22A04 完整函数体
 2. 0x229D0 的调用者与其是否比对返回
 3. 0x24800-0x24860 全景（升级序列？）
 4. A55A 立即数在全固件出现位置（判断是不是测试字）
 5. 0x23A84 函数（0x229DC 调用，返回被与 0xA55A 比较）—— 它读什么？
"""
import os
from collections import Counter
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
w("round34 —— 交叉验证：0x229D0 是自检还是真写？")
w("=" * 78)
w()

# ---------- 1. 0x229D0 完整 ----------
w("=" * 78)
w("一、0x229D0 完整函数体（含 SPI 写事务调用的那个）")
w("=" * 78)
for x in dis(0x229CE, 0x22A08):
    fo = x.address - BASE
    mk = ''
    if fo == 0x229FA: mk = '   <<<<< SPI 写事务 (cmd=2, data=0x0F9F)'
    if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
        mk += '   → 0x%05X' % (x.operands[0].imm & ~1)
    w("   0x%05X  %-10s %-32s%s" % (fo, x.mnemonic, x.op_str, mk))
w()
w("【判读】")
w("  0x229D4-0x229DC  movs r0,#0 ; bl 0x23A84 ; strh r0,[sp,#6]")
w("     ⇒ 调用 0x23A84 取回一个 16 位值")
w("  0x229E4  ldrh r0,[sp,#6]")
w("  0x229E8  movw r1,#0xA55A")
w("  0x229EC  cmp r0,r1 ; bne 0x229F4")
w("     ⇒ ★ 如果读回值 == 0xA55A 则**跳过**写；否则写 (2, 0x0F9F)")
w("  0x229F4  movs r0,#2 ; movw r1,#0x0F9F ; bl 0x1D6F0")
w("     ⇒ 参数1 = 命令/类型 = 2；参数2 = 16 位数据 = 0x0F9F")
w()

# ---------- 2. 0x23A84 是什么 ----------
w("=" * 78)
w("二、0x23A84 —— 被 0x229DC 调用，返回值与 0xA55A 比较（读什么？）")
w("=" * 78)
for x in dis(0x23A84, 0x23B10):
    fo = x.address - BASE
    mk = ''
    if fo in (0x23A84, 0x23A9C, 0x23AA0): mk = '   <<<<<'
    if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
        mk += '   → 0x%05X' % (x.operands[0].imm & ~1)
    w("   0x%05X  %-10s %-32s%s" % (fo, x.mnemonic, x.op_str, mk))
w()

# ---------- 3. 0x229D0 的调用者 ----------
w("=" * 78)
w("三、0x229D0 的调用者（判断返回值是否被比对）")
w("=" * 78)
c = find_bl_to(0x229D0, 0x229D2)
for cs, tg in sorted(c):
    w("   0x%05X" % cs)
w()
for cs, tg in sorted(c):
    w("  --- 0x%05X 上下文 ---" % cs)
    for x in dis(max(0, cs - 56), cs + 40):
        mk = '   <<<<<' if x.address - BASE == cs else ''
        w("     0x%05X  %-10s %-30s%s" % (x.address - BASE, x.mnemonic, x.op_str, mk))
    w()

# ---------- 4. 0x24800-0x24860 全景 ----------
w("=" * 78)
w("四、0x247F0 - 0x24870 全景（固件升级序列？）")
w("=" * 78)
for x in dis(0x247F0, 0x24870):
    fo = x.address - BASE
    mk = ''
    if fo in (0x24820, 0x24824, 0x24828, 0x2482C, 0x24838, 0x24848): mk = '   <<<<<'
    if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM:
        mk += '   → 0x%05X' % (x.operands[0].imm & ~1)
    w("   0x%05X  %-10s %-32s%s" % (fo, x.mnemonic, x.op_str, mk))
w()

# ---------- 5. 0xA55A / 0x5AA5 全固件扫描 ----------
w("=" * 78)
w("五、测试字扫描：0xA55A / 0x5AA5 在固件中的所有出现位置")
w("=" * 78)
for pat, nm in ((b'\x5a\xa5', '0xA55A (LE)'), (b'\xa5\x5a', '0x5AA5 (LE)')):
    pos = []
    i = D.find(pat)
    while i >= 0:
        pos.append(i); i = D.find(pat, i + 1)
    w("  %-14s x%d  %s" % (nm, len(pos), ','.join('0x%05X' % p for p in pos[:20])))
w()

# ---------- 6. 0x229D0 是否在升级相关调用图里 ----------
w("=" * 78)
w("六、0x24820 那三个 bl 的目标是什么（升级链？）")
w("=" * 78)
for t, n in ((0x1AF70, '0x1AF70'), (0x20838, '0x20838'), (0x229D0, '0x229D0'), (0x22A04, '0x22A04')):
    cc = find_bl_to(t, t + 2)
    w("  %s 被调用 %d 次: %s" % (n, len(cc), ','.join('0x%05X' % cs for cs, _ in sorted(cc))))
w()

open(os.path.join(OUTDIR, 'round34_verify.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L[:140]))
