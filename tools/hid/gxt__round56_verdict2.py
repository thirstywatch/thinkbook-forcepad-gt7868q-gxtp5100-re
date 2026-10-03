#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND56: ★ 决定性 —— 0x08019000 区到底是"只读代码"还是"可写参数区"

已知铁证 (round55):
  0x1B82C(dst,page): addr = page<<10; memcpy(dst, addr, 0x400)   <-- 纯内存读
  0x1B780(page)    : FLASH_Unlock(0x40022000 KEY1/KEY2) -> FLASH_Erase(addr=page<<10)
  0x1B9C8(buf,addr,len): FLASH_Unlock -> for each 4B: FLASH_Program -> FLASH_Lock
  => 这是一套完整的"片上 FLASH 读写驱动", addr 是真实地址

  => 0x1B874(src,off,len) 中, off+0x08019000 是写入目标地址
  => 那 0x08019000+0x1800 = 0x0801A800 会被"擦+写"

★★ 但 round49/53/54 证明 0x08019000 区是代码(290 处 BL, 80 个函数头)

  => 唯一自洽解释: ★★★ 固件运行时会"自修改代码"? 不可能这么设计
     或者: 0x1B874 的参数顺序不是 (src, off, len)!!

★★★★ 重新怀疑参数顺序:
  0x1B874 内部读的是 [sp,#0x414] 与 [sp,#0x412] 相加, 而
  [sp,#0x414] <- r1 (arg1)
  [sp,#0x412] <- r2.low16 (arg2)
  [sp,#0x418] <- r0 (arg0)  且后面当 src 用(0x1B916: ldr r0,[sp,#0x418]; ldrb [r0,r1])

  => arg0=src, arg1=off, arg2=len  --- 顺序没错

★★★★★ 真正的裁决: 检查 0x40022000 FLASH 控制器操作的【实际地址参数】
  看 0x1B9C8 里 arg1(addr) 有没有再被 +0x08019000
  以及 0x1B780 里 page<<10 有没有 +base
  => 如果 0x1B780 传的是 page<<10 (无 base), 那擦除地址 = 0..0x7000
     = flash 0x08000000..0x08007000 !! 完全不同的区域!!

  ★ 这才是关键! 让我看 0x1B874 里给 0x1B780 传的到底是
     "0x08019000+off 算出的 page"  还是  "off 算出的 page"
  从 round48: 0x1B8F8 ldr r0,[sp,#0x40c] ; bl 0x1B780
  而 [sp,#0x40c] = (0x08019000+off)>>10   (0x1B8B2-0x1B8B8)
  => 擦除地址 = ((0x08019000+off)>>10)<<10 = 0x08019000+off 的页对齐
  => 确实在 0x08019000 区!  铁证矛盾.
"""
import os, glob
from capstone import *
g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
D = open(g[0], "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB+CS_MODE_MCLASS)

# 完整打印 0x1B874 直到函数结束, 逐条列出所有对 sp+偏移 的 load/store
print("===== 0x1B874 完整数据流 (直到 pop {r7,pc}) =====")
end = None
for i in md.disasm(D[0x1B874:0x1B874+0x200], BASE+0x1B874):
    print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")
    if i.mnemonic == "pop" and "pc" in i.op_str:
        end = i.address; break

print(f"\n函数结束于 0x{end:X}" if end else "\n未找到结束")

print("\n===== 0x1B780 里 page<<10 后是否再加 base =====")
for i in md.disasm(D[0x1B780:0x1B780+0x40], BASE+0x1B780):
    print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")

print("\n===== 0x40022000 区域所有立即数引用 (确认是真 FLASH 控制器) =====")
def scan(D, lo=0x10000):
    out=[]
    for off in range(lo, len(D)-3, 2):
        hw1=int.from_bytes(D[off:off+2],"little"); hw2=int.from_bytes(D[off+2:off+4],"little")
        if ((hw1>>5)&0x1F)!=0x12 or ((hw2>>5)&0x1F)!=0x16: continue
        if ((hw1>>8)&0xF)!=((hw2>>8)&0xF): continue
        def imm16(hw): return ((hw>>10)&0x8)|((hw>>12)&0x7)|((hw>>1)&0xF00)
        v=(imm16(hw2)<<16)|imm16(hw1)
        if 0x40022000 <= v < 0x40023000: out.append((off,v))
    return out
for off,v in scan(D):
    print(f"  0x{off:X}  -> 0x{v:08X}")
