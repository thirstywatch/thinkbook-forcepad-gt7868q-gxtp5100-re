#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND40 —— 追 0x1B874 的 9 个调用者的调用者 => 找命令入口

9 个调用点: 0x1AC3E 0x1AC84 0x1AEF4 0x1AF0A 0x1BA90 0x1EFFC 0x1F10A 0x2181E 0x2190E
对这些点各自反查"谁 bl 了它们所在的函数"，逐层上追，找分派器。
"""
import sys, struct
sys.path.insert(0, r'<HOME>\.workbuddy\skills\arm-thumb-caller-trace\scripts')
from thumb_caller_trace import load_image, find_callers_of, disasm_win, find_bl_to

FW = r'<WORKSPACE>'
BASE = 0x08000000
D, _ = load_image(FW)

WRITE_WRAPPER_CALLS = [0x1AC3E, 0x1AC84, 0x1AEF4, 0x1AF0A,
                       0x1BA90, 0x1EFFC, 0x1F10A, 0x2181E, 0x2190E]

out = []
def W(s=''):
    print(s); out.append(str(s))

W("=" * 78)
W("ROUND40 追 0x1B874 的调用者的调用者")
W("=" * 78)

# ---- 1. 对每个调用点，反查谁 bl 了它 ----
W("\n## 1. 9 个调用点各自的上游\n")
upstream = {}
for c in WRITE_WRAPPER_CALLS:
    # 调用点本身未必是函数入口，所以要找"目标落在 [c-0x40, c+1) 的 bl" 太宽泛
    # 正确做法: 先看该调用点前面最近的函数序言(扫描回退找 push {...,lr} 或已知入口)
    # 这里改用: 直接反查"目标精确等于 c" 的 bl（少见），更实用的是反汇编窗口人工读
    W("--- 调用点 0x%05X ---" % c)
    for line in disasm_win(D, c - 0x20, c + 0x08, BASE):
        W("    " + line)

W("\n" + "=" * 78)
W("## 2. 以调用点为'函数入口'反查调用者（试探）")
W("=" * 78)
for c in WRITE_WRAPPER_CALLS:
    r = find_callers_of(D, c)
    W("0x%05X <- %d 个调用者 %s" % (c, len(r), [hex(x) for x, _ in r][:10]))

open('cfg_parsed/round40_entry.txt', 'w', encoding='utf-8').write('\n'.join(out))
print("\n[已写 cfg_parsed/round40_entry.txt]")
