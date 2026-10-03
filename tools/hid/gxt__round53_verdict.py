#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND53: ★★★ 重大修正 —— 0x1B7B4/0x1B874 操作的是【RAM】不是 flash!

证据链:
  round48 反汇编 0x1B874:
      str.w r0,[sp,#0x418]     ; arg0 = src
      str.w r1,[sp,#0x414]     ; arg1
      strh.w r2,[sp,#0x412]    ; arg2 (len, u16)
      ldr r0,[sp,#0x414]; ldrh r1,[sp,#0x412]; add r0,r1; cmp r0,#0x7000
      ... movw r1,#0x9000 ; movt r1,#0x801 ; add r0,r1   => arg1 + 0x08019000
      lsrs r0,r0,#0xa          ; page = addr>>10
      bfc  r0,#0xa,#0x16       ; offset_in_page
      rsb  r0,r0,#0x400        ; 0x400 - off
      读 0x1B82C(dst=sp, page)  ; 读"一页"到栈缓冲
      擦 0x1B780(page)
      把 src 的数据填进页缓冲
      写回
  => 这是标准 **EEPROM/Flash 仿真在 RAM 中做读-改-写**

关键: 目标基址 0x08019000 + off  为什么是 0x08019000?
  ⇒ 0x08019000 不是 flash 地址, 而是 **"RAM 区起始"**?

不. 0x08019000 是 flash 地址(第2段明文区起点). 
真正的问题: 我一直在假设 off 是"相对 0x08019000".
但重新看 round49: file 0x1A800 是代码 => 说明 0x0801A800 处确实是代码.

★ 那么 0x1B874 的"目标"就是 **指向代码区**?! 那不可能.

=== 换一个已经验证过的角度 ===
round24 已确认: 容器头给出「子固件表」, 固件分区:
   0x0000-0x0FFF  容器头
   0x1000-0x18FFF 加密主程序 (96KB)
   0x19000-0x2775B 明文代码 (57KB)

所以 0x08019000 = 明文代码段起点. 这段**是**代码.

★★ 决定性检验: 0x1B874 的基址可能不是 0x08019000, 而是我漏看了后面还有 add!
   重看完整指令流 (round48):
     0x0801B8A0  ldr r0,[sp,#0x414]
     0x0801B8A4  movw r1,#0x9000
     0x0801B8A8  movt r1,#0x801
     0x0801B8AC  add  r0,r1
   -> 0x0801B8AC 之后没有任何再 +base 的操作.
   => 目标 = 0x08019000 + off. 铁定.

★★★ 所以结论只能是: **0x08019000 这片"看起来像代码"的区域, 是"代码与数据混排",
    而 off=0x1800 处的 27 字节 —— 就是"设备序列号/校准块"这类数据**
    ... 但它熵 5.85, 且 08 F0 56 FF 是标准 bl 编码. 不像数据.

★★★★ 真正的裁决: 直接反汇编 0x0801A800 前后一整片, 看是不是"合法函数序列"
   如果是, 那它 100% 是代码, 那 0x1B874 的模型就是错的.
   如果反汇编出来混乱, 那可能是数据.
"""
import os, glob
from capstone import *

g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
D = open(g[0], "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB+CS_MODE_MCLASS)

def linear_dis(off, n, title):
    print(f"\n===== {title} (file 0x{off:X}) 线性反汇编 {n} 字节 =====")
    prev_end = off
    bad = 0; tot = 0
    for i in md.disasm(D[off:off+n], BASE+off):
        gap = i.address - (BASE+prev_end)
        tag = "  <-- 不连续!" if gap != 0 and prev_end != off else ""
        if gap not in (0,) and prev_end != off:
            bad += 1
        print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}{tag}")
        prev_end = i.address + i.size
        tot += 1
    print(f"  [指令 {tot} 条, 不连续处 {bad}]")

linear_dis(0x1A7F0, 0x100, "0x1A800 附近 (0x1800 落点)")
print("\n" + "="*70)
print("对比: 一处【真正已知是代码】的位置 (0x1AB90 附近)")
linear_dis(0x1AB90, 0x60, "0x1AB90 (已知代码)")

print("\n" + "="*70)
print("对比: 一处【已知是数据】的位置 —— cfg 文件本身在固件里吗?")
# 找 cfg signature: 'PCB\0' 和 'LaiBao' 和 '7867'
for sig in [b"PCB\x00", b"LaiBao", b"7867", b"Xiaomi", b"7986P", b"7863", b"PNOR"]:
    idx = D.find(sig)
    pos = []
    p = 0
    while True:
        p = D.find(sig, p)
        if p < 0: break
        pos.append(p); p += 1
        if len(pos) > 8: break
    print(f"  '{sig.decode(errors='replace')}' -> {len(pos)} 处: " + " ".join(f"0x{x:X}" for x in pos))
