# -*- coding: utf-8 -*-
# 第二十轮：尾部 ARM Thumb-2 完整反汇编（自做）
import os, sys, struct
from collections import Counter, defaultdict

try:
    from capstone import *
    from capstone.arm import *
except ImportError:
    print("ERROR: capstone 未安装"); sys.exit(1)

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed')
os.makedirs(OUTDIR, exist_ok=True)

BASE = 0x08000000          # 假设：文件偏移 0 == 运行地址 0x08000000（需验证）

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = True

w("="*78)
w("尾部 ARM Thumb-2 反汇编（第二十轮）")
w("="*78)

# ---------- 0. 基址假说验证 ----------
w()
w("### 0. 文件偏移 → 运行地址 基址的验证")
w("  已知：0x19ECC 处字符串 TF100A_Test_FW，0x264EE 处 5.21.01.23007")
w("  已知：代码里出现 0x0801xxxx / 0x20004xxx 等地址常量")
w("  检验法：把已知字符串偏移 + 候选基址，看代码里有没有指向它的地址常量。")
for candbase, nm in [(0x08000000,'0x08000000'), (0x08010000,'0x08010000'), (0,'0(裸偏移)')]:
    # 找指向 0x19ECC 的常量
    for s_off, s_nm in [(0x19ECC,'TF100A_Test_FW'), (0x264EE,'5.21.01.23007'), (0x261C0,'hexdigit')]:
        tgt = candbase + s_off
        pat = struct.pack('<I', tgt)
        n = D.count(pat)
        # 也试 +1（thumb 位）
        pat1 = struct.pack('<I', tgt | 1)
        n1 = D.count(pat1)
        if n or n1:
            w("    base=%s  目标 %s(0x%05X) -> 0x%08X : 命中 %d 次 (+1 变体 %d)" % (nm, s_nm, s_off, tgt, n, n1))
    # 统计该基址下的所有地址常量分布
w()
w("  另一种验证：统计 MOVW/MOVT 解出的地址，看哪些落在字符串区")
# MOVW/MOVT
def dec(off):
    if off + 4 > len(D): return None
    hw1 = D[off] | (D[off+1] << 8); hw2 = D[off+2] | (D[off+3] << 8)
    if (hw1 >> 11) != 0b11110: return None
    op = hw1 & 0x0FF0
    if op not in (0x240, 0x2C0): return None
    imm4 = hw1 & 0xF; i = (hw1 >> 10) & 1; imm3 = (hw2 >> 12) & 7
    rd = (hw2 >> 8) & 0xF; imm8 = hw2 & 0xFF
    return ('MOVW' if op == 0x240 else 'MOVT'), rd, (imm4 << 12) | (i << 11) | (imm3 << 8) | imm8
def pairs(lo, hi):
    mw = {}; mt = {}; out = []
    for off in range(lo & ~1, hi - 3, 2):
        r = dec(off)
        if not r: continue
        k, rd, imm = r
        (mw if k == 'MOVW' else mt)[off] = (rd, imm)
    for o1, (r1, i1) in mw.items():
        for d in (2, 4, 6, 8, 10, 12):
            o2 = o1 + d
            if o2 in mt and mt[o2][0] == r1:
                out.append((o1, r1, (mt[o2][1] << 16) | i1)); break
    return out
allp = pairs(0x19800, len(D))
addrs = Counter(a for _, _, a in allp)
w("    MOVW/MOVT 解出的地址（0x19800-END 内）共 %d 组，唯一 %d 个" % (len(allp), len(addrs)))
filt = {a:c for a,c in addrs.items() if not (0x08000000 <= a < 0x08200000 or 0x20000000 <= a < 0x20020000
        or 0x40000000 <= a < 0x60000000 or 0xE0000000 <= a < 0xE0100000)}
w("    非标准段的地址（可疑/可能是偏移而非绝对地址）: %d 个" % len(filt))
for a, c in sorted(filt.items(), key=lambda x:-x[1])[:15]:
    w("      0x%08X  x%d" % (a, c))

# ---------- 1. 函数边界 ----------
w()
w("### 1. 函数边界（PUSH{...,LR} 起，BX LR / POP{PC} 止）")
starts = []
i = 0x19800
while i < len(D) - 3:
    hw = D[i] | (D[i+1] << 8)
    if 0xB400 <= hw <= 0xB5FF and (hw & 0x0100) and (hw & 0x00FF):
        starts.append(i)
    i += 2
w("  候选起点(PUSH{...,LR}) %d 个" % len(starts))

funcs = []
for s in starts:
    j = s; end = None
    LIM = min(s + 3000, len(D) - 3)
    while j < LIM:
        hw = D[j] | (D[j+1] << 8)
        if hw == 0x4770: end = j + 2; break
        if 0xBD00 <= hw <= 0xBDFF: end = j + 2; break
        # 也要能识别 32 位 POP.W: E8BD xxxx
        if hw == 0xE8BD: end = j + 4; break
        j += 2
    if end:
        funcs.append((s, end))
# 去掉嵌套
funcs.sort()
clean = []
for s, e in funcs:
    if clean and s < clean[-1][1]:
        continue
    clean.append((s, e))
w("  配对成功 %d / 去嵌套后 %d 个函数" % (len(funcs), len(clean)))
lens = [e-s for s, e in clean]
w("  长度: 最短 %d  中位 %d  最长 %d  平均 %.0f  总计 %d B" %
  (min(lens), sorted(lens)[len(lens)//2], max(lens), sum(lens)/len(lens), sum(lens)))

# ---------- 2. 逐个函数反汇编 ----------
w()
w("### 2. 函数索引（含 MOVW/MOVT 引用地址）")
frecs = []
for idx, (s, e) in enumerate(clean):
    code = D[s:e]
    insns = list(md.disasm(code, BASE + s))
    bad = sum(1 for ins in insns if ins.mnemonic.startswith('udf') or ins.mnemonic == '.byte')
    mnems = Counter(ins.mnemonic for ins in insns)
    # 该函数内的地址常量
    fp = [a for off, rd, a in allp if s <= off < e]
    frecs.append(dict(idx=idx, s=s, e=e, n=len(insns), bad=bad, mnems=mnems, addrs=fp))
w("  总指令数 %d" % sum(f['n'] for f in frecs))

for f in frecs[:40]:
    w("   F%-3d 0x%05X-0x%05X (%4dB) %4d条 bad=%d  %s" % (
        f['idx'], f['s'], f['e'], f['e']-f['s'], f['n'], f['bad'],
        'addrs=' + ','.join('0x%08X' % a for a in f['addrs'][:4]) if f['addrs'] else ''))

# ---------- 3. 助记符频次 ----------
w()
w("### 3. 全局助记符频次 top-30")
allmn = Counter()
for f in frecs:
    allmn.update(f['mnems'])
for m, n in allmn.most_common(30):
    w("    %-14s %d" % (m, n))

# ---------- 4. BL 目标 ----------
w()
w("### 4. BL / BLX 调用目标")
bl_t = Counter()
for f in frecs:
    code = D[f['s']:f['e']]
    for ins in md.disasm(code, BASE + f['s']):
        if ins.mnemonic in ('bl', 'blx') and ins.operands:
            op = ins.operands[0]
            if op.type == ARM_OP_IMM:
                bl_t[op.imm & ~1] += 1
w("  唯一目标 %d 个，总调用 %d 次" % (len(bl_t), sum(bl_t.values())))
w("  被调最多 top-25（含是否落在文件内）:")
for t, n in bl_t.most_common(25):
    fo = t - BASE
    tag = ('文件内 0x%05X' % fo) if 0 <= fo < len(D) else '文件外'
    w("    0x%08X  x%-3d  %s" % (t, n, tag))

open(os.path.join(OUTDIR, 'disasm_tail.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
