# -*- coding: utf-8 -*-
"""
round30_spi_caller.py —— 追 0x40003000 (SPI/EEPROM 命令口) 的调用者

目标：回答「0x40003000 背后挂的是哪颗器件」。
方法：从该基址的全部 MOVW/MOVT 装载点出发，反汇编其所在函数，
      建立调用图（谁 bl 谁），并把每个访问点前后的立即数/寄存器流打出来。
输出：cfg_parsed/round30_spi_caller.txt
"""
import os, struct
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

# ---------- 基础工具 ----------
def dec_mov(off):
    """解码一条 MOVW/MOVT，返回 (kind, rd, imm16) 或 None"""
    if off + 4 > len(D): return None
    hw1 = D[off] | (D[off+1] << 8); hw2 = D[off+2] | (D[off+3] << 8)
    if (hw1 >> 11) != 0b11110: return None
    op = hw1 & 0x0FF0
    if op not in (0x240, 0x2C0): return None
    imm4 = hw1 & 0xF; i = (hw1 >> 10) & 1; imm3 = (hw2 >> 12) & 7
    return ('MOVW' if op == 0x240 else 'MOVT'), (hw2 >> 8) & 0xF, \
           (imm4 << 12) | (i << 11) | (imm3 << 8) | (hw2 & 0xFF)

# 全段 MOVW/MOVT 配对
mw = {}; mt = {}
for off in range(0x18000 & ~1, len(D) - 3, 2):
    r = dec_mov(off)
    if not r: continue
    k, rd, imm = r
    (mw if k == 'MOVW' else mt)[off] = (rd, imm)
PAIRS = []
for o1, (r1, i1) in mw.items():
    for d in (2, 4, 6, 8, 10, 12, 14, 16):
        o2 = o1 + d
        if o2 in mt and mt[o2][0] == r1:
            PAIRS.append((o1, r1, (mt[o2][1] << 16) | i1, o2)); break

# ---------- 函数边界（与 disasm_tail 同法） ----------
starts = []
i = 0x19000
while i < len(D) - 3:
    hw = D[i] | (D[i+1] << 8)
    if 0xB400 <= hw <= 0xB5FF and (hw & 0x0100) and (hw & 0x00FF):
        starts.append(i)
    i += 2
rawf = []
for s in starts:
    j = s; end = None
    LIM = min(s + 4000, len(D) - 3)
    while j < LIM:
        hw = D[j] | (D[j+1] << 8)
        if hw == 0x4770: end = j + 2; break
        if 0xBD00 <= hw <= 0xBDFF: end = j + 2; break
        if hw == 0xE8BD: end = j + 4; break
        j += 2
    if end: rawf.append((s, end))
rawf.sort()
FUNCS = []
for s, e in rawf:
    if FUNCS and s < FUNCS[-1][1]: continue
    FUNCS.append((s, e))

def owner(off):
    for s, e in FUNCS:
        if s <= off < e: return (s, e)
    return None

def dis(lo, hi, base=None):
    return list(md.disasm(D[lo:hi], (BASE if base is None else base) + lo))

def fname(s):
    return 'F@0x%05X' % s

# ---------- 全量 BL 调用图 ----------
CALLS = defaultdict(set)       # caller_start -> set(callee_addr)
CALLSITE = defaultdict(list)   # callee_addr  -> [(callsite_off, caller_start)]
for s, e in FUNCS:
    for ins in dis(s, e):
        if ins.mnemonic in ('bl', 'blx') and ins.operands and ins.operands[0].type == ARM_OP_IMM:
            tgt = ins.operands[0].imm & ~1
            CALLS[s].add(tgt)
            CALLSITE[tgt].append((ins.address - BASE, s))

w("=" * 78)
w("round30 —— 追 0x40003000 (SPI/EEPROM 命令口) 的调用者")
w("=" * 78)
w()
w("固件: %s" % os.path.basename(FW))
w("大小: %d B   函数总数: %d   基址: 文件偏移 0 = 0x%08X" % (len(D), len(FUNCS), BASE))
w()

# ============================================================
# 1. 0x40003000 的全部引用点
# ============================================================
w("=" * 78)
w("一、0x40003000 基址的全部 MOVW/MOVT 装载点")
w("=" * 78)
SITES = [(o1, a, a - 0x40003000, rd, o2) for o1, rd, a, o2 in PAIRS
         if 0x40003000 <= a < 0x40003400]
w("共 %d 处" % len(SITES))
for o1, a, ro, rd, o2 in sorted(SITES):
    w("   0x%05X  R%-2d = 0x%08X   (0x40003000 + 0x%02X)   所在函数 %s" %
      (o1, rd, a, ro, fname(owner(o1)[0]) if owner(o1) else '??'))
w()

# 同时找 0x40003000 附近 ±0x400 的所有外设基址（看看还有谁）
NEAR = [(o1, a, rd) for o1, rd, a, o2 in PAIRS if 0x40000000 <= a < 0x40008000]
nearcnt = Counter(a for _, a, _ in NEAR)
w("【参照】0x40000000-0x40008000 区间内所有 MOVW/MOVT 常量（按地址）:")
for a, n in sorted(nearcnt.items()):
    off = a - 0x40000000
    sites = [('0x%05X' % o1) for o1, aa, _ in NEAR if aa == a]
    w("   0x%08X (APB1+0x%05X) x%-2d  %s" % (a, off, n, ','.join(sites[:8])))
w()

# ============================================================
# 2. 关键函数完整反汇编
# ============================================================
KEY_FUNCS = sorted(set(owner(o1)[0] for o1, a, ro, rd, o2 in SITES if owner(o1)))
w("=" * 78)
w("二、涉及 0x40003000 的函数（完整反汇编）")
w("=" * 78)
for fs in KEY_FUNCS:
    fe = dict(FUNCS)[fs]
    ins = dis(fs, fe)
    w()
    w("-" * 78)
    w("### %s   0x%05X - 0x%05X  (%d B, %d 条指令)" % (fname(fs), fs, fe, fe - fs, len(ins)))
    w("-" * 78)
    for x in ins:
        fo = x.address - BASE
        mark = ''
        for o1, a, ro, rd, o2 in SITES:
            if fo == o1: mark = '   <<<<< 0x40003000 (+0x%02X)' % ro
        # 标注寄存器被赋了什么常量
        if fo in dict((o, (rd, ad)) for o, rd, ad, _ in PAIRS):
            rd, ad = [v for o, v in PAIRS_dict.items() if o == fo][0] if False else (None, None)
        w("   0x%05X  %-10s %s%s" % (fo, x.mnemonic, x.op_str, mark))
    w()
    # 该函数内的 BL 目标
    bls = [(x.address - BASE, x.operands[0].imm & ~1) for x in ins
           if x.mnemonic in ('bl', 'blx') and x.operands and x.operands[0].type == ARM_OP_IMM]
    if bls:
        w("   -> 本函数调用: %s" % ', '.join('0x%05X->%s' % (cs, fname(t - BASE)) if owner(t - BASE) else '0x%05X->外部' % cs for cs, t in bls))
        w()
    # 该函数内的地址常量
    faddrs = sorted(set(a for o, rd, a, _ in PAIRS if fs <= o < fe))
    if faddrs:
        w("   -> 本函数内 MOVW/MOVT 常量: %s" % ', '.join('0x%08X' % a for a in faddrs))
        w()

w("=" * 78)
w("三、0x40003000 的调用者链（谁调用上面这些函数）")
w("=" * 78)
for fs in KEY_FUNCS:
    tgt = BASE + fs
    callers = CALLSITE.get(tgt, [])
    w()
    w("  %s (0x%05X) 被调用 %d 次:" % (fname(fs), fs, len(callers)))
    for cs, cstart in callers:
        w("     从 0x%05X 调用（调用者 %s）" % (cs, fname(cstart)))

# 二级：这些调用者自身又被谁调用
w()
w("  二级调用者（对上面每个调用者再往上追一层）:")
SEEN = set(KEY_FUNCS)
for fs in KEY_FUNCS:
    for cs, cstart in CALLSITE.get(BASE + fs, []):
        lvl2 = CALLSITE.get(BASE + cstart, [])
        w("     %s  <- %s" % (fname(cstart), ', '.join('%s@0x%05X' % (fname(s2), c2) for c2, s2 in lvl2) or '(无)'))

open(os.path.join(OUTDIR, 'round30_spi_caller.txt'), 'w', encoding='utf-8').write('\n'.join(L))
print('\n'.join(L))
