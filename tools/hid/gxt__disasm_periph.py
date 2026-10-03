# -*- coding: utf-8 -*-
# 第二十轮 B：外设访问地图 + I2C 从地址搜寻 + FLASH 编程序列还原
import os, struct
from collections import Counter, defaultdict
from capstone import *
from capstone.arm import *

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
BASE = 0x08000000
OUT = []
def w(s=''):
    OUT.append(s)
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed')

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS); md.detail = True

w("="*78)
w("第二十轮 B：外设访问地图 + I2C + FLASH 序列")
w("="*78)

# ---------- MOVW/MOVT 全量配对 ----------
def dec(off):
    if off + 4 > len(D): return None
    hw1 = D[off] | (D[off+1] << 8); hw2 = D[off+2] | (D[off+3] << 8)
    if (hw1 >> 11) != 0b11110: return None
    op = hw1 & 0x0FF0
    if op not in (0x240, 0x2C0): return None
    imm4 = hw1 & 0xF; i = (hw1 >> 10) & 1; imm3 = (hw2 >> 12) & 7
    return ('MOVW' if op == 0x240 else 'MOVT'), (hw2 >> 8) & 0xF, (imm4 << 12) | (i << 11) | (imm3 << 8) | (hw2 & 0xFF)

mwp = {}   # off -> (rd, imm16)  MOVW
mtp = {}
for off in range(0x19800 & ~1, len(D) - 3, 2):
    r = dec(off)
    if not r: continue
    k, rd, imm = r
    if k == 'MOVW': mwp[off] = (rd, imm)
    else: mtp[off] = (rd, imm)
PAIRS = []   # (movw_off, rd, addr32, movt_off)
for o1, (r1, i1) in mwp.items():
    for d in (2, 4, 6, 8, 10, 12):
        o2 = o1 + d
        if o2 in mtp and mtp[o2][0] == r1:
            PAIRS.append((o1, r1, (mtp[o2][1] << 16) | i1, o2))
            break

# ---------- 1. 外设访问地图 ----------
w()
w("### 1. 外设访问地图（按外设基址分组，给出代码偏移与寄存器偏移）")
PERIPH = {
    0x40005400: 'I2C1',
    0x40012400: 'ADC1',
    0x40021000: 'RCC',
    0x40022000: 'FLASH',
    0x40020000: 'GPIOA',
    0x40020400: 'GPIOB',
    0x40020800: 'GPIOC',
    0x40010800: 'GPIO?',
    0x40010000: 'APB2',
    0x40000000: 'APB1',
    0x48000000: 'AHB2-GPIO',
    0xE000E010: 'SysTick',
    0xE000E100: 'NVIC-ISER',
    0xE000E400: 'NVIC-IPR',
}
byper = defaultdict(list)
for o1, rd, a, o2 in PAIRS:
    for base, nm in PERIPH.items():
        if base <= a < base + 0x400 or (base == 0xE000E010 and 0xE000E000 <= a < 0xE000F000):
            byper[nm].append((o1, a, a - base, rd))
            break
for nm in sorted(byper, key=lambda k: -len(byper[k])):
    lst = byper[nm]
    w()
    w("  【%s】 %d 次访问" % (nm, len(lst)))
    regs = Counter(off for _, _, off, _ in lst)
    for roff, n in sorted(regs.items()):
        locs = [('0x%05X' % o1) for o1, _, ro, _ in lst if ro == roff][:6]
        w("     基址+0x%03X  x%-2d  出现于 %s" % (roff, n, ','.join(locs)))

# ---------- 2. I2C 从地址搜寻 ----------
w()
w("### 2. ★ I2C 从地址搜寻（决定触觉芯片是否独立）")
w("  方法：I2C1 基址 0x40005400。找所有「MOVW/MOVT 载入 0x400054xx」附近出现的立即数写入。")
i2c_sites = [(o1, a, a-0x40005400, rd) for o1, rd, a, o2 in PAIRS if 0x40005400 <= a < 0x40005800]
w("  I2C1 寄存器引用 %d 处" % len(i2c_sites))
for o1, a, ro, rd in sorted(i2c_sites):
    w("    0x%05X  R%d = 0x%08X  (I2C1+0x%03X)" % (o1, rd, a, ro))

w()
w("  ★ 在这些引用点前后 64 B 内，找形如 'movs rX, #imm' 的立即数（可能是从地址）：")
addrs_found = Counter()
for o1, a, ro, rd in i2c_sites:
    lo = max(0x19800, o1 - 64); hi = min(len(D), o1 + 96)
    for ins in md.disasm(D[lo:hi], BASE + lo):
        if ins.mnemonic in ('movs', 'mov', 'mov.w') and ins.operands:
            op = ins.operands[-1]
            if op.type == ARM_OP_IMM:
                if 0x08 <= op.imm <= 0xFE and op.imm % 2 == 0:
                    addrs_found[op.imm] += 1
                    w("      0x%05X  %-8s #0x%02X" % (ins.address - BASE, ins.mnemonic, op.imm))
w()
w("  候选 7-bit 从地址（立即数>>1），按出现频次：")
for v, n in addrs_found.most_common(20):
    w("    立即数 0x%02X  -> 7bit 0x%02X  x%d" % (v, v >> 1, n))

w()
w("  ★ 直接在 I2C 相关函数里搜从地址常量（全文件扫描，看哪些偶数立即数被反复用于 I2C）：")
# 全文件 common values
w("  全文件里 0x50-0x60 / 0xA0-0xC0 范围的字节频次（I2C 地址常见区）：")
c = Counter(D)
for v in range(0x50, 0x62):
    if c[v]: w("    0x%02X x%d (7bit 0x%02X)" % (v, c[v], v >> 1))
for v in range(0xA0, 0xC2, 2):
    if c[v]: w("    0x%02X x%d (7bit 0x%02X)" % (v, c[v], v >> 1))

# ---------- 3. FLASH 编程序列 ----------
w()
w("### 3. ★ FLASH 编程序列还原（KEY1 = 0x45670123）")
key1 = struct.pack('<I', 0x45670123)
key2 = struct.pack('<I', 0xCDEF89AB)
k1pos = [i for i in range(len(D)-3) if D[i:i+4] == key1]
w("  KEY1 (0x45670123) 出现在: %s" % ','.join('0x%05X' % p for p in k1pos))
for kp in k1pos:
    w()
    w("  --- KEY1 @ 0x%05X 上下文反汇编 ---" % kp)
    lo = max(0, kp - 96); hi = min(len(D), kp + 128)
    for ins in md.disasm(D[lo:hi], BASE + lo):
        mark = ''
        if kp <= ins.address - BASE < kp + 4: mark = '   <<<< KEY1'
        w("    0x%05X  %-8s %s%s" % (ins.address - BASE, ins.mnemonic, ins.op_str, mark))
w()
w("  ★ KEY2 (0xCDEF89AB) 出现次数: %d" % len([i for i in range(len(D)-3) if D[i:i+4] == key2]))
w("  ★ 反向检验：这两个常量在**真随机文件**里出现概率 ~ 0 ⇒ 命中即为真实现")
# FLASH 寄存器访问
w()
w("  FLASH 寄存器被写的偏移（0x40022000 基址）:")
fl = [(o1, a-0x40022000, rd) for o1, rd, a, o2 in PAIRS if 0x40022000 <= a < 0x40022400]
for ro, n in sorted(Counter(x[1] for x in fl).items()):
    names = {0x00:'ACR',0x04:'KEYR',0x08:'OPTKEYR',0x0C:'SR',0x10:'CR',0x14:'AR',0x18:'RESERVED',0x1C:'OBR',0x20:'WRPR'}
    # STM32F1: 0x00 ACR, 0x04 KEYR, 0x08 OPTKEYR, 0x0C SR, 0x10 CR, 0x14 AR
    w("    +0x%02X (%s)  x%d" % (ro, names.get(ro, '?'), n))

# ---------- 4. 字符串交叉引用 ----------
w()
w("### 4. ★ 字符串交叉引用（哪些代码引用了构建标识/版本/格式串）")
STRS = [(0x19ECC, 'TF100A_Test_FW'), (0x19EEC, 'Nov 28 2023'), (0x19F0C, '19:10:59'),
        (0x261C0, 'hexlower'), (0x261D4, 'hexupper'), (0x264EE, '5.21.01.23007'),
        (0x264FC, '%d\\r\\n')]
for soff, sname in STRS:
    tgt = BASE + soff
    pat = struct.pack('<I', tgt); pat1 = struct.pack('<I', tgt | 1)
    n0 = D.count(pat); n1 = D.count(pat1)
    # MOVW/MOVT 解出该地址？
    via = [('0x%05X' % o1) for o1, rd, a, o2 in PAIRS if a == tgt or a == (tgt | 1)]
    w("  %-14s (0x%05X) 直字面量 %d/%d  MOVW/MOVT 引用 %s" %
      (sname, soff, n0, n1, ','.join(via) if via else '无'))
    for v in via[:3]:
        w("      -> 引用点 %s 反汇编：" % v)
        o = int(v, 16); lo = max(0, o-16); hi = min(len(D), o+32)
        for ins in md.disasm(D[lo:hi], BASE+lo):
            w("         0x%05X  %-8s %s" % (ins.address-BASE, ins.mnemonic, ins.op_str))

# ---------- 5. 参数表区（0x00000-0x01200）性质复核 ----------
w()
w("### 5. 0x00000-0x01200 性质复核（子代理说不是 8051）")
seg = D[0:0x1200]
w("  熵 %.4f  零占比 %.4f" % (
    -sum((v/len(seg))*__import__('math').log2(v/len(seg)) for v in Counter(seg).values()),
    seg.count(0)/len(seg)))
w("  用 capstone 尝试 Thumb 反汇编前 256 B（看非法率）：")
ins = list(md.disasm(D[0:256], BASE))
bad = sum(1 for i in ins if i.mnemonic.startswith('udf'))
w("    Thumb 反汇编 %d 条，udf %d 条 (%.3f)" % (len(ins), bad, bad/max(1,len(ins))))
w("  该区能否被识别为 8051？关键操作码密度（/KB）:")
n = len(seg)
for nm, op in [('0x75 MOV dir,#imm',0x75), ('0xE0 MOVX A,@DPTR',0xE0), ('0x12 LCALL',0x12),
               ('0x22 RET',0x22), ('0x90 MOV DPTR',0x90), ('0xA3 INC DPTR',0xA3)]:
    cnt = seg.count(op)
    w("    %-22s %4d  (%.1f/KB)  随机期望 %.1f/KB" % (nm, cnt, cnt/(n/1024), 1024/256))
w("  ⇒ 若关键操作码密度无一显著高于随机 ⇒ 不是 8051 代码")

open(os.path.join(OUTDIR, 'disasm_periph.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
