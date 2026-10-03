#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ec_xor.py -- 定位并提取 .text 里的 XOR/rol 解码循环。

已确认（推翻上一轮的错误结论）：
  · .text 有 147 处【真 XOR】（a≠b）和 25 处 rol/ror
  · 上一轮"找不到 XOR 循环"是我的正则写错了（要求 xor 下一条必须是 mov[x]，
    而真实代码里 xor 常跟 xor/add/movzx/inc 组合）—— 教训见纪律

本轮目标：把 147 处 XOR 逐个定位，筛出"在循环里、对内存做读-改-写"的那几个
  —— 那就是 payload 解码循环。
判据（结构化，不靠肉眼）：
  L1  紧邻 loop/jnz 回跳（构成回边）
  L2  xor 的两个操作数里有一个是 [reg+idx]（内存操作数）
  L3  附近有 inc/add 推进指针
"""
import struct, re, collections
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_REG, X86_OP_MEM, X86_OP_IMM

FN = 'NJME01WW.exe'
d = open(FN, 'rb').read()
pe = struct.unpack_from('<I', d, 0x3C)[0]
imgbase = struct.unpack_from('<I', d, pe + 24 + 28)[0]
nsec = struct.unpack_from('<H', d, pe + 6)[0]
optsz = struct.unpack_from('<H', d, pe + 20)[0]
sec0 = pe + 24 + optsz
tra = rsz = None
for i in range(nsec):
    q = sec0 + i * 40
    nm = d[q:q + 8].rstrip(b'\x00').decode('latin1')
    vsz, va, ssz, ra = struct.unpack_from('<IIII', d, q + 8)
    if nm == '.text':
        tra, rsz, tva = ra, ssz, va
text = d[tra:tra + rsz]
base = imgbase + tva

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True
md.skipdata = True
ins = list(md.disasm(text, base))
idx = {i.address: k for k, i in enumerate(ins)}
print('反汇编 %d 条' % len(ins))

# 回边：跳转目标地址 < 当前地址，且距离 < 200 B
backedges = []
for k, i in enumerate(ins):
    if i.mnemonic.startswith('j'):
        m = re.match(r'^(?:j\w+\s+)?0x([0-9a-f]+)$', i.op_str)
        if m:
            tgt = int(m.group(1), 16)
            if tgt < i.address and i.address - tgt < 200:
                backedges.append((tgt, i.address))

loops = collections.defaultdict(list)
for lo, hi in backedges:
    loops[lo].append(hi)
print('回边(短跳转)数: %d，形成 %d 个循环头' % (len(backedges), len(loops)))


def in_loop(addr, span=400):
    for lo, hi in backedges:
        if lo <= addr <= hi or (lo <= addr <= lo + span and addr <= hi):
            return True
    return False


print()
print('=' * 92)
print('★ 候选解码循环：含【对内存做 XOR】且在回边内')
print('=' * 92)
cands = []
for k, i in enumerate(ins):
    if i.mnemonic != 'xor':
        continue
    ops = [o for o in i.operands]
    if len(ops) != 2:
        continue
    if ops[0].type == X86_OP_REG and ops[1].type == X86_OP_REG and \
            ops[0].reg == ops[1].reg:
        continue
    has_mem = any(o.type == X86_OP_MEM for o in ops)
    if not has_mem:
        continue
    if not in_loop(i.address):
        continue
    cands.append((i.address, i.op_str, k))

print('候选: %d 处' % len(cands))
for va, ops, k in cands[:40]:
    off = va - base + tra
    # 打印上下文 ±6 条
    lo = max(0, k - 6)
    print('\n  --- 0x%08X (file 0x%06X)  xor %s ---' % (va, off, ops))
    for j in range(lo, min(len(ins), k + 7)):
        m = '>>' if j == k else '  '
        print('   %s 0x%08X  %-8s %s' % (m, ins[j].address, ins[j].mnemonic, ins[j].op_str))
