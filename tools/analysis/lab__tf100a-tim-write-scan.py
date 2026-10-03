#!/usr/bin/env python3
# tf100a-tim-write-scan.py —— 搜 TF100A 里【结构体间接】写定时器寄存器的地方
#
# 动机：此前判"CCR 运行期不变"的依据是「字面量 0x40000034 搜不到 + HAL 0x08010908 只有一个调用者」。
#       但代码惯用结构体间接（ldr rBase,[struct,#4] 然后 str rX,[rBase,#off]），
#       这种情况下字面量搜索必然漏掉。
#
# 定时器寄存器偏移（STM32 风格）：
#   0x00 CR1   0x04 CR2   0x08 SMCR  0x0C DIER  0x10 SR   0x14 EGR
#   0x18 CCMR1 0x1C CCMR2 0x20 CCER  0x24 CNT   0x28 PSC  0x2C ARR
#   0x34 CCR1  0x38 CCR2  0x3C CCR3  0x40 CCR4
#
# 输出：每个命中点的地址 + 前后各 4 行上下文，便于判断是否在运行期路径上。

import re, sys

ASM = r"<WORKSPACE>"
lines = open(ASM, encoding='utf-8', errors='ignore').read().splitlines()

# 解析成 (addr, mnem, ops)
recs = []
pat = re.compile(r'^\s*([0-9a-f]{8})\s+(\S+)\s*(.*)$')
for i, l in enumerate(lines):
    m = pat.match(l)
    if m:
        recs.append((int(m.group(1), 16), m.group(2), m.group(3).strip(), i))

# 关注写寄存器（str/strh/strb），偏移是定时器关键寄存器
KEY = {0x00: 'CR1', 0x0C: 'DIER', 0x14: 'EGR', 0x18: 'CCMR1', 0x1C: 'CCMR2',
       0x20: 'CCER', 0x24: 'CNT', 0x28: 'PSC', 0x2C: 'ARR',
       0x34: 'CCR1', 0x38: 'CCR2', 0x3C: 'CCR3', 0x40: 'CCR4'}

hits = []
for addr, mnem, ops, i in recs:
    if not mnem.startswith('str'):
        continue
    m = re.match(r'(r\d+),\s*\[(r\d+)(?:,\s*#(0x[0-9a-f]+))?\]', ops)
    if not m:
        continue
    off = int(m.group(3), 16) if m.group(3) else 0
    if off in KEY:
        hits.append((addr, mnem, ops, i, off, m.group(2)))

print(f"TF100A 反汇编共 {len(recs)} 条指令")
print(f"★ 写定时器关键寄存器偏移（结构体间接）的指令：{len(hits)} 处\n")
from collections import Counter
print("按偏移统计:", Counter(f"0x{o:02X}({KEY[o]})" for _,_,_,_,o,_ in hits).most_common())
print()

# 重点：CCR1/CCR2/CCER/PSC/ARR 的命中点 + 上下文
FOCUS = {0x34, 0x38, 0x20, 0x28, 0x2C, 0x18, 0x1C, 0x00}
for addr, mnem, ops, i, off, basereg in hits:
    if off not in FOCUS:
        continue
    print("=" * 74)
    print(f"0x{addr:08X}  {mnem} {ops}      ← 偏移 0x{off:02X} = {KEY[off]}   基址寄存器={basereg}")
    for k in range(max(0, i - 5), min(len(lines), i + 3)):
        mark = "  >>" if k == i else "    "
        print(f"{mark} {lines[k].rstrip()}")
