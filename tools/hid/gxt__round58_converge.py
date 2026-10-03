#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND58: ★ 收敛 —— 判定"0x1B874 写 0x1800"这条路径的真实性

已建立的事实(全部可复现):
 F1. 0x1B82C(dst,page) = memcpy(dst, page<<10, 0x400)           [纯内存读]
 F2. 0x1B780(page) = FLASH_Unlock; FLASH_Erase(page<<10); Lock  [真 FLASH 控制器]
 F3. 0x1B874(src,off,len): 目标 = 0x08019000+off, 按 1KB 页读改写
 F4. 0x08019000 区(file 0x19000..) = 明文 Thumb 代码:
     290 处 BL 目标落在该区, 80 个 push{...,lr} 函数头, 交叉引用自洽
 F5. file 0x1A800 附近反汇编 = 完整合法函数序列

 矛盾: F3 的目标 0x0801A800 是 F4/F5 证明的"代码", 却被当作可擦写参数区

★ 唯一自洽解释(候选Z):
   【本次拿到的是"出厂完整镜像", 而设备运行时该镜像被重新布局】
   即: 固件被烧进 SPI flash 后, 运行时 0x08019000 映射到的不是
   "镜像 file 0x19000", 而是被 bootloader 搬运过的 RAM 副本.
   但 Cortex-M 上 0x08000000 是 flash 别名, 不会在运行时被写...

★ 候选Y(可能性最高):
   ★★★ 0x1B874 的 arg1(off) 与 arg2 的关系被我读错:
   重看 0x1B882: strh.w r2,[sp,#0x412]   <-- arg2 存 u16
   0x1B88A: ldrh.w r1,[sp,#0x412]        <-- 取 arg2
   0x1B88E: add r0,r1                    <-- r0 = arg1 + arg2
   => 若 arg1=0x1800, arg2=0x1B: 0x181B ✓ 通过 <0x7000 检查
   => 目标 = 0x08019000 + 0x1800

   但 ★ 0x1B7B4(读) 里: 
   0x1B7DA: ldr r1,[sp,#0xc]        r1 = arg1(off)
   0x1B7DC: movw r2,#0x9000 movt r2,#0x801   r2 = 0x08019000
   0x1B7E4: add r1,r2               r1 = 0x08019000 + off
   0x1B806: ldr r2,[sp,#2]          循环变量
   0x1B80A: strb r0,[r1,r2]         目标[r2] = 源[r2]
   => 一致, 目标 = 0x08019000+off

★ 结论(诚实记录):
   两条独立路径(读/写)都指向 0x08019000+off, 且该处在镜像中是代码.
   => 存在两种可能:
      (a) 该固件镜像的这部分在设备上被【运行时重映射/重定位】过
      (b) 我们读出的镜像与设备内实际运行的镜像【不是同一份布局】
   无论哪种, 都说明:
   ★★★ 【不能仅凭静态镜像断言 0x1800 的语义】—— 0x1800 是"逻辑扇区偏移",
       其物理落点取决于运行时的内存布局, 静态无法唯一确定.

★ 可操作结论:
   命令 0x1B / 0x3200 是对"逻辑参数区 off=0x1800, 长度 0x1B(27B)"的读写,
   这是一对【读-写镜像命令】, 语义上是"设备配置块"(27 字节).
   与主机交互: 主机可读回 27B, 也可写 27B.
   风险: 写这 27B 若落在【代码段】会导致固件损坏;
        若落在【参数段】则只是配置变更.
   => 在无法确认物理落点前, ★ 不建议盲写.
"""
import os, glob, hashlib
g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
D = open(g[0], "rb").read()

print("=== 1. 检查镜像内是否存在【同一 27B 块】的多个副本 ===")
# 取 file 0x1A800 的 27 字节
blk = D[0x1A800:0x1A800+0x1B]
print("  file 0x1A800 27B:", blk.hex())
cnt = 0
p = 0
while True:
    p = D.find(blk, p)
    if p < 0: break
    cnt += 1; p += 1
print(f"  该 27B 在镜像中出现 {cnt} 次: ", end="")
p = 0; pos=[]
while True:
    p = D.find(blk, p)
    if p < 0: break
    pos.append(p); p += 1
print(" ".join(f"0x{x:X}" for x in pos))

print("\n=== 2. cfg 头 'PCB\\0' / 'LaiBao' 是否在镜像中 (确认参数区是否被包进镜像) ===")
for sig in [b"PCB\x00", b"LaiBao", b"Xiaomi", b"7867", b"7986P"]:
    ps=[]; p=0
    while True:
        p=D.find(sig,p)
        if p<0: break
        ps.append(p); p+=1
        if len(ps)>10: break
    print(f"  {sig!r}: {len(ps)} 处 {[hex(x) for x in ps]}")

print("\n=== 3. 0x1800 附近的『页』(0x1A800..0x1ABFF, 1KB) 熵 ===")
import math, collections
def ent(b):
    c=collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
print(f"  file 0x1A800..0x1ABFF ent = {ent(D[0x1A800:0x1AC00]):.3f}")

print("\n=== 4. 关键对照: 若 0x1800 是【相对 flash 数据区(非代码区)】的偏移 ===")
print("  cfg 数据块(sid0=1302B) 在镜像中找不到 => 参数区不在这个 BIN 里")
print("  => 说明 TB14P_....BIN 是【程序镜像】, 参数区是【设备内单独存储/由 cfg 烧录】")
