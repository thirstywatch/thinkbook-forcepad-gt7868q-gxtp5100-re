#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND44 —— 纠错 + 收口

★ 纠错: ROUND22 的"28KB 是配置区不是代码区"**判据错误**。
  实际: 写入基址 0x08019000, 上限 0x7000 是 **偏移上限**（不是绝对地址），
  所以可写窗口 = 0x08019000 .. 0x08020000 (28 KB, 文件偏移 0x19000..0x20000)。
  而 0x1B874 / 0x1B780 自己就在 0x1Bxxx —— **落在窗口内**。
  该窗口熵 5.5~6.5、含 push{lr}/bx lr/b.n 序列、含 "TF100A_Test_FW" 字符串
  => 这是 **代码段（含 TF100A 子固件区）**，不是配置区。

本脚本: 精确收集所有写入/读取调用点实际使用的偏移常量，确定改写目标。
"""
import sys
sys.path.insert(0, r'<HOME>\.workbuddy\skills\arm-thumb-caller-trace\scripts')
from thumb_caller_trace import load_image, disasm_win

FW = r'<WORKSPACE>'
BASE = 0x08000000
D, _ = load_image(FW)

out = []
def W(s=''):
    print(s); out.append(str(s))

W("=" * 78)
W("ROUND44 纠错 + 写入目标偏移精确收集")
W("=" * 78)

W("\n## A. ★ 纠错：可写窗口的真实边界\n")
W("  0x1B8A4  movw r1,#0x9000 ; movt r1,#0x801   =>  r1 = 0x08019000")
W("  0x1B8AC  add  r0, r1                          =>  addr += 0x08019000")
W("  0x1B890  cmp.w r0,#0x7000  (在 add 之前，对原始 addr 判)")
W("  => 可写窗口 = 0x08019000 + [0, 0x7000) = 0x08019000..0x08020000")
W("  => 文件偏移 0x19000..0x20000，共 28 KB")
W("")
W("  ⚠️ ROUND22 说这是'配置区'是**判据错误** ——")
W("     0x1B874(写入封装)、0x1B780(擦页) 自身就在 0x1Bxxx，**落在窗口内**；")
W("     窗口内熵 5.5~6.5、见 push{lr}(b580)/bx lr(4770)/b.n(e7ff) 指令序列、")
W("     并且含 'TF100A_Test_FW' 与编译时间戳 —— 这是**代码段**。")

W("\n## B. 窗口内关键锚点\n")
W("  0x19ECC  'TF100A_Test_FW'   <- 钛方 TF100A 压力前端的固件标识")
W("  0x19EEC  'Nov 28 2023'      <- 编译日期")
W("  0x19F0C  '19:10:59'         <- 编译时间")
W("  0x1B874  写入封装本体（在窗口内！）")
W("  0x1B780  擦页函数（在窗口内！）")
W("  0x1B9C8  写整页函数")
W("  0x1BCA0  写 4 字节")
W("  0x1B7B4  从 0x08019000 拷贝（读）")

W("\n## C. 9 个写入调用点的偏移常量（第三个参数 r1）\n")
CALLS = [0x1AC3E, 0x1AC84, 0x1AEF4, 0x1AF0A, 0x1BA90, 0x1EFFC, 0x1F10A, 0x2181E, 0x2190E]
for c in CALLS:
    W("--- 调用点 0x%05X（前 16 字节）---" % c)
    for l in disasm_win(D, c - 0x10, c + 0x02, BASE):
        W("      " + l)

W("\n## D. 0x1B7B4（读函数）的调用者\n")
from thumb_caller_trace import find_callers_of
r = find_callers_of(D, 0x1B7B4)
W("  共 %d 个：" % len(r))
for c, _ in r:
    W("    0x%05X" % c)
W("")
for c, _ in r:
    W("--- 读取调用点 0x%05X ---" % c)
    for l in disasm_win(D, c - 0x14, c + 0x02, BASE):
        W("      " + l)

open('cfg_parsed/round44_correction.txt', 'w', encoding='utf-8').write('\n'.join(out))
print("\n[已写 cfg_parsed/round44_correction.txt]")
