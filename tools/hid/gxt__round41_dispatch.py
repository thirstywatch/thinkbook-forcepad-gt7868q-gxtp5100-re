#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND41 —— 定位 9 个写入调用的宿主函数 + 找命令分派器

策略:
  A. 用"向后扫描最近函数序言"确定每个调用点的宿主函数入口
  B. 对每个宿主入口反查调用者
  C. 找 0x1BA7C (最简写入小函数) 的调用者 => 大概率是 cfg setter
  D. 找含 cmp rX,#imm 且 imm 覆盖 0x1b/0x1c 等值的分派器
"""
import sys
sys.path.insert(0, r'<HOME>\.workbuddy\skills\arm-thumb-caller-trace\scripts')
from thumb_caller_trace import load_image, find_callers_of, disasm_win

FW = r'<WORKSPACE>'
BASE = 0x08000000
D, _ = load_image(FW)

out = []
def W(s=''):
    print(s); out.append(str(s))

CALLS = [0x1AC3E, 0x1AC84, 0x1AEF4, 0x1AF0A, 0x1BA90, 0x1EFFC, 0x1F10A, 0x2181E, 0x2190E]

# ---- A. 向后找函数序言 ----
def find_prologue(D, off, back=0x200):
    """从 off 向前找 push {...} 或 sub sp 形式，返回最近的函数入口候选"""
    cands = []
    for o in range(off, max(0, off - back), -2):
        hw = D[o] | (D[o+1] << 8)
        # push {...,lr} = 0xB5xx (PUSH 且含 lr)，或 32 位 push.w 的 0xE92D
        if (hw & 0xFF00) == 0xB500:
            cands.append((o, 'push{lr} 0x%04X' % hw)); break
        if hw == 0xE92D:
            hw2 = D[o+2] | (D[o+3] << 8)
            if hw2 & 0x4000:      # 含 LR
                cands.append((o, 'push.w{lr} 0x%04X' % hw2)); break
    return cands[0] if cands else None

W("=" * 78)
W("ROUND41 宿主函数定位 + 命令分派器搜索")
W("=" * 78)

W("\n## A. 每个写入调用点的宿主函数入口\n")
hosts = {}
for c in CALLS:
    p = find_prologue(D, c)
    if p:
        hosts[c] = p[0]
        W("  调用 0x%05X  宿主入口 0x%05X  (%s)" % (c, p[0], p[1]))
    else:
        W("  调用 0x%05X  未找到序言" % c)

W("\n## B. 各宿主入口的调用者\n")
for c, h in sorted(hosts.items()):
    r = find_callers_of(D, h)
    W("  宿主 0x%05X <- %d 个调用者: %s" % (h, len(r), [hex(x) for x, _ in r][:12]))

# ---- C. 最简写入小函数 0x1BA7C ----
W("\n## C. 最简写入函数体 0x1BA7C 及其实体\n")
for line in disasm_win(D, 0x1BA7C, 0x1BA9C, BASE):
    W("    " + line)

W("\n## D. 含 cmp #0x1b / #0x1c 的代码位置（分派器线索）\n")
# cmp rX, #0x1b 编在 Thumb 里: 0x2E1B (cmp r6,#0x1b) 等；直接扫字节
hits = []
for o in range(0x10000, len(D) - 2, 2):
    hw = D[o] | (D[o+1] << 8)
    # CMP imm8 T1: 001 00 Rd imm8  => 0x28xx..0x2Fxx
    if (hw & 0xF800) == 0x2800:
        rd = (hw >> 8) & 7
        imm = hw & 0xFF
        if imm in (0x1b, 0x1c, 0x1d, 0x1e):
            hits.append((o, rd, imm))
W("  命中 %d 处：" % len(hits))
for o, rd, imm in hits[:60]:
    W("    0x%05X  cmp r%d, #0x%02X" % (o, rd, imm))

W("\n## E. 0x1AEF4 宿主（0x1ABC0 附近）上下文：看是不是 cfg 写回\n")
for line in disasm_win(D, 0x1AE00, 0x1AF20, BASE):
    W("    " + line)

open('cfg_parsed/round41_dispatch.txt', 'w', encoding='utf-8').write('\n'.join(out))
print("\n[已写 cfg_parsed/round41_dispatch.txt]")
