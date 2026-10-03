#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND43 —— 任务2：解 0x08019000 处 28 KB 数据的性质
             任务3：确认 0x1B7B4 的调用者读的是什么
"""
import sys, struct, collections
sys.path.insert(0, r'<HOME>\.workbuddy\skills\arm-thumb-caller-trace\scripts')
from thumb_caller_trace import load_image, disasm_win, find_callers_of, find_bl_to

FW = r'<WORKSPACE>'
BASE = 0x08000000
D, _ = load_image(FW)

out = []
def W(s=''):
    print(s); out.append(str(s))

REGION_LO, REGION_HI = 0x19000, 0x26000

W("=" * 78)
W("ROUND43 任务2: 0x%05X 处 %d KB 数据结构分析" % (REGION_LO, (REGION_HI - REGION_LO) // 1024))
W("=" * 78)

# ---- A. 分页熵/熵图 ----
import math
def ent(b):
    if not b: return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v/n) * math.log2(v/n) for v in c.values())

W("\n## A. 逐 1KB 页熵 + 特征（结构化程度）\n")
W("    页号  文件偏移   熵    非零率  可打印率  重复度(最高字节占比)  前16字节")
for pg in range(REGION_LO, REGION_HI, 0x400):
    blk = D[pg:pg + 0x400]
    e = ent(blk)
    nz = sum(1 for x in blk if x) / len(blk)
    pr = sum(1 for x in blk if 0x20 <= x < 0x7F) / len(blk)
    c = collections.Counter(blk)
    top = max(c.values()) / len(blk)
    W("    %3d   0x%05X  %5.2f   %5.1f%%   %5.1f%%     %5.1f%%          %s"
      % ((pg - REGION_LO) // 0x400, pg, e, nz * 100, pr * 100, top * 100,
         blk[:16].hex(' ')))

# ---- B. 该区域内的 ASCII 字符串 ----
W("\n## B. 区域内的 ASCII 字符串（长度>=5）\n")
import re
s = D[REGION_LO:REGION_HI]
found = []
for m in re.finditer(rb'[\x20-\x7E]{5,}', s):
    found.append((REGION_LO + m.start(), m.group().decode('ascii', 'replace')))
W("  共 %d 条：" % len(found))
for off, t in found[:80]:
    W("    0x%05X  %s" % (off, t))

# ---- C. 区域头部结构 ----
W("\n## C. 区域起始 0x19000 的头部 256 字节 hexdump\n")
for i in range(0, 256, 16):
    row = D[REGION_LO + i: REGION_LO + i + 16]
    W("    0x%05X  %s  |%s|" % (REGION_LO + i, row.hex(' '),
      ''.join(chr(c) if 0x20 <= c < 0x7F else '.' for c in row)))

# ---- D. 任务3: 0x1B7B4 的调用者 ----
W("\n" + "=" * 78)
W("ROUND43 任务3: 0x1B7B4 的调用者读的是什么")
W("=" * 78)

W("\n## D. 0x1B7B4 函数体\n")
for l in disasm_win(D, 0x1B7B4, 0x1B830, BASE):
    W("    " + l)

r = find_callers_of(D, 0x1B7B4)
W("\n## E. 0x1B7B4 调用者：%d 个\n" % len(r))
for c, _ in r:
    W("    0x%05X" % c)

W("\n## F. 各调用点上下文（看第二个参数 = 区域偏移）\n")
for c, _ in r:
    W("--- 调用点 0x%05X ---" % c)
    for l in disasm_win(D, c - 0x18, c + 0x06, BASE):
        W("    " + l)

# ---- G. 收集所有传给 0x1B874/0x1B7B4 的偏移常量 ----
W("\n## G. 传给写入/读取函数的偏移常量（r1 立即数）\n")
offs = collections.Counter()
for off in range(0x10000, len(D) - 4, 2):
    r0 = find_bl_to(D, 0x1B874, 0x1B876, scan_lo=off, scan_hi=off + 1)
    if not r0: continue
W("  (改用直接扫描调用点前的 movw/movs 立即数)")
CALLS_W = [0x1AC3E, 0x1AC84, 0x1AEF4, 0x1AF0A, 0x1BA90, 0x1EFFC, 0x1F10A, 0x2181E, 0x2190E]
for c in CALLS_W:
    for l in disasm_win(D, c - 0x0C, c, BASE):
        if 'r1' in l and ('mov' in l or 'add' in l):
            W("    0x%05X  %s" % (c, l.strip()))

open('cfg_parsed/round43_region.txt', 'w', encoding='utf-8').write('\n'.join(out))
print("\n[已写 cfg_parsed/round43_region.txt]")
