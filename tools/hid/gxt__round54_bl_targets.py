#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND54: 用"逐指令精确重放"的方式, 铁证判定 0x1B874 的目标地址公式
不使用启发式, 直接把 0x1B874 从头到尾每条指令对寄存器/栈的影响打出来.

已知 (round48 原文):
  0801B874  80b5        push  {r7,lr}
  0801B876  adf5846d    sub.w sp, sp, #0x420
  0801B87A  cdf81804    str.w r0, [sp,#0x418]      arg0
  0801B87E  cdf81414    str.w r1, [sp,#0x414]      arg1
  0801B882  adf81224    strh.w r2, [sp,#0x412]     arg2 (u16)
  ...
  0801B886  ddf81404    ldr.w r0, [sp,#0x414]      r0 = arg1
  0801B88A  bdf81214    ldrh.w r1, [sp,#0x412]     r1 = arg2
  0801B88E  0844        add   r0, r1               r0 = arg1+arg2
  0801B890  b0f5e04f    cmp.w r0, #0x7000
  0801B894  04d3        blo   0x801B8A0            if <0x7000 goto
  0801B896  ffe7        b     0x801B898            (永真跳转)
  ...

★ 注意 0801B894 是条件分支, 0801B896 是 b (无条件). 
  capstone 把 0801B896 显示为 b 0x801B898, 这是正确反汇编(尾调用)。
  但 !! 0801B88E 的 add r0,r1 后面 0801B890 cmp.w r0,#0x7000
  => 这要求 r0=arg1 = 一个"偏移", 且 arg1+arg2 < 0x7000

★ 关键: 如果 arg1 是 flash 偏移(0x1800), arg2 是长度(0x1B) => 0x181B < 0x7000 ✓

★ 那目标地址 = 0x08019000 + arg1 = 0x0801A800  <-- 这里是代码!
  这是硬矛盾.

★★ 可能性: 0x08019000 不是"flash基址", 而是编译器把 0x08019000 当作一个
   **"内存映射基址别名"** —— 即芯片上有一块外设/EEPROM 被映射到 0x08019000?
   但 0x08019000 在 flash 别名区 (0x08000000..) 内.

★★★ 最终检查: 看整个固件里是否"有代码在 0x08019000 处被调用"
   如果有 => 0x08019000 确实是可执行代码 => flash 库模型错
   如果没有 => 0x08019000 可能是"数据区", 只是数据恰好长得像代码
   检验: 找所有 bl/bx/b 的目标落在 [0x08019000, 0x08020000) 的
"""
import os, glob, collections
from capstone import *

g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
D = open(g[0], "rb").read()
BASE = 0x08000000

def decode_bl_off(D, off):
    hw1 = int.from_bytes(D[off:off+2],"little"); hw2 = int.from_bytes(D[off+2:off+4],"little")
    if (hw1 & 0xF800) != 0xF000: return None
    if (hw2 & 0xD000) != 0xD000: return None
    s = (hw1>>10)&1; j1=(hw2>>13)&1; j2=(hw2>>11)&1
    i1=(~(s^j1))&1; i2=(~(s^j2))&1
    imm = (s<<24)|(i1<<23)|(i2<<22)|((hw1&0x3FF)<<12)|((hw2&0x7FF)<<1)
    if imm & 0x1000000: imm -= 0x2000000
    return off + 4 + imm

print("=== 所有 BL 目标落在 [0x19000,0x20000) 的调用 (rt 0x08019000..0x0801FFFF) ===")
hits = []
for off in range(0x10000, len(D)-4, 2):
    t = decode_bl_off(D, off)
    if t is not None and 0x19000 <= t < 0x20000:
        hits.append((off, t))
print(f"命中 {len(hits)} 处")
for off, t in hits[:60]:
    print(f"  caller 0x{off:X} (rt 0x{BASE+off:08X})  ->  target 0x{t:X}")

print("\n=== 统计: 调用目标分布 (按 4KB 段) ===")
c = collections.Counter(t & ~0xFFF for _, t in hits)
for seg, n in sorted(c.items()):
    print(f"  0x{seg:05X}..0x{seg+0xFFF:05X}: {n}")

print("\n=== 反向: [0x19000,0x20000) 内代码有没有被调用 (抽样看是否有函数头) ===")
# 检查 0x19000..0x20000 中有多少处 push {...,lr}
cnt = 0
for off in range(0x19000, 0x20000, 2):
    if int.from_bytes(D[off:off+2],"little") in (0xB580, 0xB5F0, 0xB570, 0xB510, 0xB500):
        cnt += 1
print(f"  0x19000..0x20000 内 push{{...,lr}} 模式 {cnt} 处 / {0x7000//2} 半字")
print(f"  平均每 0x{(0x7000//cnt):X} 字节一个函数头" if cnt else "")
