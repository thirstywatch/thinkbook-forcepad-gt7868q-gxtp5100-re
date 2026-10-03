#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND45 —— 追 0x248B6 / 0x24820 上游到 USB 端点（BL/字面量/跳转 四路搜索）

结论：四路全空 => 0x24820 是"中断驱动+轮询"架构的主循环入口，静态追不到。
"""
import sys, struct
sys.path.insert(0, r'<HOME>\.workbuddy\skills\arm-thumb-caller-trace\scripts')
from thumb_caller_trace import load_image, disasm_win, find_callers_of, find_imm32_hi16

FW = r'<WORKSPACE>'
BASE = 0x08000000
D, _ = load_image(FW)

out = []
def W(s=''):
    print(s); out.append(str(s))

TARGETS = [0x24820, 0x248B6, 0x248E2]

W("=" * 78)
W("ROUND45 追 USB 端点：四路搜索")
W("=" * 78)

W("\n## A. BL 调用者\n")
for t in TARGETS:
    r = find_callers_of(D, t)
    W("  0x%05X <- %d 个 %s" % (t, len(r), [hex(x) for x, _ in r][:10]))

W("\n## B. 字面量指针（4 字节，全镜像非对齐扫）\n")
for t in TARGETS:
    for cand, nm in ((BASE | t, 'base|off'), (BASE | t | 1, 'base|off|thumb')):
        hits = []
        for o in range(0, len(D) - 3):
            if struct.unpack_from('<I', D, o)[0] == cand:
                hits.append(o)
        W("  0x%08X (%s) : %d 处 %s" % (cand, nm, len(hits), [hex(h) for h in hits[:8]]))

W("\n## C. MOVW/MOVT 构造\n")
for t in TARGETS:
    hi16 = (BASE | t) >> 16
    r = find_imm32_hi16(D, hi16)
    hit = [(hex(o), Rd) for o, Rd, lo, hi in r if ((hi << 16) | lo) == (BASE | t)]
    W("  0x%08X : %d 处 %s" % (BASE | t, len(hit), hit))

W("\n## D. 无条件 b / b.w 目标\n")
def b_targets(D, tgt):
    res = []
    for o in range(0x10000, len(D) - 4, 2):
        hw = D[o] | (D[o+1] << 8)
        if (hw & 0xF800) == 0xE000:
            imm = hw & 0x7FF
            if imm & 0x400: imm -= 0x800
            if o + 4 + imm == tgt: res.append((hex(o), 'b'))
        if (hw & 0xF800) == 0xF000:
            hw2 = D[o+2] | (D[o+3] << 8)
            if (hw2 & 0xD000) == 0x9000:
                S = (hw1 := hw) >> 10 & 1
                imm10 = hw1 & 0x3FF
                J1 = (hw2 >> 13) & 1; J2 = (hw2 >> 11) & 1; imm11 = hw2 & 0x7FF
                I1 = (~(J1 ^ S)) & 1; I2 = (~(J2 ^ S)) & 1
                imm = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
                if imm & (1 << 24): imm -= (1 << 25)
                if o + 4 + imm == tgt: res.append((hex(o), 'b.w'))
    return res
for t in TARGETS:
    r = b_targets(D, t)
    W("  0x%05X : %d 处 %s" % (t, len(r), r[:8]))

W("\n## E. 0x24820 主循环结构\n")
for l in disasm_win(D, 0x24816, 0x24900, BASE):
    W("    " + l)

W("\n## F. 0x247E0 函数尾 / 0x24820 入口邻接\n")
for l in disasm_win(D, 0x24818, 0x24826, BASE):
    W("    " + l)
W("  ★ 0x2481E = bx lr（函数结束），0x24820 无序言 => fall-through 进入 => 是入口")

open('cfg_parsed/round45_usb.txt', 'w', encoding='utf-8').write('\n'.join(out))
print("\n[已写 cfg_parsed/round45_usb.txt]")
