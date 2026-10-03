#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND57: ★★★★ 最终模型裁决 —— 参数顺序 / 地址语义 的两种候选,

候选A: 0x1B874(src, off, len); 目标 = 0x08019000+off (片上FLASH)
       => 与"0x08019000区是代码(290处BL)"矛盾 ✗

候选B: 0x1B874 的 arg1 不是"off", 而是**已经是绝对地址**
       调用方传的是 0x001800 之类, 是某个"逻辑扇区号"?
       不, 0x1B8A4 明确 add 0x08019000

候选C: ★ 代码区的 0x08019000 与"写入目标 0x08019000" 是**不同的物理介质**,
       靠【地址别名】区分: 
         - 取指时 0x08019000 走 I-Bus -> flash 代码区
         - 数据写时 0x08019000 走 D-Bus -> 被重映射到别的存储
       这在 STM32 上不成立(统一编址)

候选D: ★★ 参数顺序其实是 (src, len, off)? 
       0x1B874: [0x414]=arg1, [0x412]=arg2(low16)
       add r0 = arg1 + arg2 ; cmp 0x7000
       => 若是 (src,len,off): arg1=len, arg2=off, 那 add 还是 = len+off
       然后 add r0, 0x08019000 用的还是 arg1
       => 同 A, 无差别

候选E: ★★★ 0x08019000 处的确"既是代码又会被擦写", 因为
       0x1B874 从来【没有】以 off=0x1800 被真正调用过!
       即: 那条路径是"死代码" —— 只在特定条件下走, 实际设备上可能
       因为 gating 条件(0x20004128 bit2 等)不满足而永不执行.

★★★★★ 决定性的检查(本次): 
     0x1B874 的 9 个 caller, 有哪几个是"主循环/周期性"可达的?
     已在 round24 确认主循环 0x24820 调 0x229D0(校准写回) 等.
     而 0x22C7C(命令分发器) 调用的 0x1BA7C/0x1AC30 等 —— 
     它们只在【主机下发命令】时执行!

     => 所以"写 0x1800"是【主机命令 0x3200】触发的, 而不是固件自发!
     => 那么固件设计者认为 0x0801A800 是"可写的参数区"
     => 但我们的固件镜像里那里是代码 => 说明【镜像与运行时不符】!!

     ★ 这是核心洞察: 我们从 SPI flash 芯片里读出的镜像 = 完整固件镜像,
       包含了"代码段"和"参数段". 但固件运行时会:
       ① 把某些段搬到 RAM (0x20000000+)
       ② 参数区的"逻辑地址" 0x08019000 可能对应镜像中的一个【子镜像】

     所以 0x08019000 不是"file offset 0x19000"! 它可能是
     "参数子区在 flash 中的另一个位置" —— 但我门已证明 file 0x19000 是代码.

★★★★★★ 真正的终极检验: 在镜像里搜索"27 字节的参数块特征"
     即 cmd 0x1B 读出的 27 字节, 应该是一个有结构的配置块.
     既然 0x0801A800 是代码, 那真正的参数块在镜像别处.
     => 找 27 字节的、被多处引用的、低熵的块
     => 或者: 找 cfg 的 TLV 结构在镜像中的位置
"""
import os, glob, math, collections

g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
D = open(g[0], "rb").read()
print("image size:", len(D), hex(len(D)))

def ent(b):
    if not b: return 0.0
    c=collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

# ── 1. 全镜像 4KB 熵图, 标出"低熵(候选参数区)" ──
print("\n=== 全镜像 4KB 页熵 (只列 熵<5.5 的, 即可能是数据/参数/填充) ===")
low = []
for p in range(0, len(D), 0x1000):
    b = D[p:p+0x1000]
    if len(b) < 0x400: continue
    e = ent(b)
    if e < 5.5:
        low.append((p, e))
for p, e in low:
    print(f"  file 0x{p:05X} (rt 0x{0x08000000+p:08X})  ent {e:.3f}")

print("\n=== 全镜像 4KB 页熵 (每页) ===")
for p in range(0, len(D), 0x2000):
    b = D[p:p+0x2000]
    e = ent(b)
    print(f"  file 0x{p:05X}  ent {e:.3f}")

# ── 2. 找可能的"参数块": 长度 27 且反复出现的结构 ──
print("\n=== 检查 0x08000000 基址的 flash 读写模型 (对比库) ===")
# 扫 movw/movt 得 0x08000000 系列基址
found = collections.Counter()
for off in range(0x10000, len(D)-3, 2):
    hw1=int.from_bytes(D[off:off+2],"little"); hw2=int.from_bytes(D[off+2:off+4],"little")
    if ((hw1>>5)&0x1F)!=0x12 or ((hw2>>5)&0x1F)!=0x16: continue
    if ((hw1>>8)&0xF)!=((hw2>>8)&0xF): continue
    def imm16(hw): return ((hw>>10)&0x8)|((hw>>12)&0x7)|((hw>>1)&0xF00)
    v=(imm16(hw2)<<16)|imm16(hw1)
    if 0x08000000<=v<0x08028000: found[v]+=1
print("  [0x08000000,0x08028000) 内出现的 imm32 (按频次):")
for v,c in sorted(found.items(), key=lambda x:-x[1])[:25]:
    print(f"    0x{v:08X}  x{c}")
