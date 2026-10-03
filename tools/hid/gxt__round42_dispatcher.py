#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND42 —— 完整解出命令分派器

分派器入口 0x22C7C:
  - 检查 0x20004128 bit2 (协议使能标志)
  - r0 = 报文指针; [r0+0x104] = 报文类型; 0x80 = 一类, 0xA0 = 命令类
  - [0x20004940] = 当前报文指针
  - r0 = [报文+2] (16 位大端? 小端?) = 命令号
  - 一长串 cmp.w + beq 分派到各 case
  - 每个 case 尾 b 0x22E80 -> 置 0x20004946=1 -> b 0x23202

本脚本:
  A. 完整提取命令号 -> case 地址 的映射表
  B. 反查分派器 0x22C7C 的调用者
  C. 反汇编 0x1AB90 段（cmp r0,#0x1B 处）确认其角色
"""
import sys, struct
sys.path.insert(0, r'<HOME>\.workbuddy\skills\arm-thumb-caller-trace\scripts')
from thumb_caller_trace import load_image, disasm_win, find_callers_of

FW = r'<WORKSPACE>'
BASE = 0x08000000
D, _ = load_image(FW)

out = []
def W(s=''):
    print(s); out.append(str(s))

W("=" * 78)
W("ROUND42 命令分派器 0x22C7C 完整解出")
W("=" * 78)

# ---- A. 提取分派表 ----
W("\n## A. 命令号 -> case 地址 映射（扫描 0x22CE4-0x22D8A 的 cmp.w/beq 序列）\n")
tbl = []
o = 0x22CEE
end = 0x22D8A
while o < end:
    for line in disasm_win(D, o, min(o + 0x20, end + 4), BASE):
        # 形如: 0x022CF0  cmp.w    r0, #0x500
        pass
    o += 2
# 直接手解：用 capstone 顺序遍历
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
code = D[0x22CE4:0x22D8C]
seq = list(md.disasm(code, BASE + 0x22CE4))
i = 0
while i < len(seq):
    ins = seq[i]
    if ins.mnemonic.startswith('cmp') and '#' in ins.op_str:
        val = int(ins.op_str.split('#')[1], 16)
        # 找紧随的 beq
        tgt = None
        for j in range(i + 1, min(i + 4, len(seq))):
            if seq[j].mnemonic.startswith('beq'):
                tgt = int(seq[j].op_str.lstrip('#'), 16)
                break
        if tgt:
            tbl.append((val, tgt))
    i += 1

W("  共 %d 条命令分支：" % len(tbl))
seen = set()
for val, tgt in tbl:
    if (val, tgt) in seen: continue
    seen.add((val, tgt))
    W("    命令 0x%04X  ->  case 0x%08X" % (val, tgt))

# ---- B. 分派器调用者 ----
W("\n## B. 分派器 0x22C7C 的调用者\n")
r = find_callers_of(D, 0x22C7C)
W("  0x22C7C <- %d 个调用者: %s" % (len(r), [hex(x) for x, _ in r][:20]))
r2 = find_callers_of(D, 0x22C78)   # 也可能是入口(ands r0,r0 是填充)
W("  0x22C78 <- %d 个调用者: %s" % (len(r2), [hex(x) for x, _ in r2][:20]))

# ---- C. 0x1AB90 段 ----
W("\n## C. 0x1AB90 段（含 cmp r0,#0x1B 的另一处）\n")
for line in disasm_win(D, 0x1AB50, 0x1AC00, BASE):
    W("    " + line)

# ---- D. 写 0x1B 的那个 case 完整体 ----
W("\n## D. case 0x3200 -> 0x22E52（写字节 0x1B 到 [报文+4]）\n")
for line in disasm_win(D, 0x22E52, 0x22E66, BASE):
    W("    " + line)

open('cfg_parsed/round42_dispatcher.txt', 'w', encoding='utf-8').write('\n'.join(out))
print("\n[已写 cfg_parsed/round42_dispatcher.txt]")
