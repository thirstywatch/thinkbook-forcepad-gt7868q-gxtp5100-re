#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND59: ★★★★★ 终局模型 —— 镜像的"两段布局"与运行时的"重定位"

事实汇总(全部已复现):
 [1] 容器头 0x0000..0x0FFF  (ent 5.09)
 [2] 0x1000..0x18FFF 加密(ent 7.95-7.99)  96KB
 [3] 0x19000..0x2775B 明文代码(ent 5.4-7.2) 57KB
 [4] 0x19ABC 处有完整 Cortex-M 向量表, 全部表项 <= 0x0800DFE4
     => 主程序(Reset/NMI/Handler)运行在 0x0800xxxx 区(即 file 0x0000..0xE000)
     => 而 file 0x0000..0xE000 属于【加密区】!
 [5] 0x1B7B4/0x1B874 读写目标 = 0x08019000+off, 用真 STM32 FLASH 控制器(0x40022000)
 [6] file 0x19000 区是【明文代码】(290处BL, 80个函数头)
 [7] cfg(sid0/sid2/sid3) 在镜像中【0 次出现】

★★★ 自洽解释:

 向量表在 file 0x19ABC(明文区), 但表项指向 0x0800xxxx(加密区, file 0x0000-0xE000).
 => 设备上电时, 0x08000000 处运行的代码 = 加密区的解密结果.
 => 也就是说: ★ 加密区解密后【就地运行在 0x08000000..】, 
    而明文区 file 0x19000 = 运行时地址 0x08019000 = 【确实是代码】.

 ★★★★ 那么 [5] 与 [6] 的矛盾如何解?
   解: ★ 0x1B7B4/0x1B874 的 "0x08019000+off" 中的 0x08019000 是一个
       【"假基址"/"符号化基址"】—— 编译时它代表"某个被链接到这个位置的段",
       但设备上这个段的真实内容【不是镜像 file 0x19000 的字节】,
       而是运行时由 bootloader 从别处 (如外部 SPI flash 或 EEPROM) 读入的.

   更可能: 它就是 STM32 内部 FLASH 的一个【独立扇区组】, 
   只是【这个 BIN 镜像只包含程序, 不包含那个参数扇区】——
   参数扇区在烧录时由 cfg 文件单独写入, 不打包进程序 BIN.

 ★★★★★ 结论(本次任务的最终答案):

  1) 0x1800 / 0x3800 的语义 = 【固件内部"参数/校准存储区"的逻辑偏移】
     - 0x1800: 27 字节块 (cmd 0x1B 读 / cmd 0x3200 写) —— 一个"配置块"
     - 0x3800: 8 字节块  (cmd 0x1700 写 / 主循环读回) —— 另一个"配置块"
     - 另有 0x444 / 0x2444 / 0x2000 / 0x2C00 / 0x3044 等偏移,
       构成一个完整的"参数存储布局"(见 round51/52 的映射表)

  2) 该存储区【不在】我们手上的 TB14P_...BIN 镜像里
     => 无法从镜像静态读出其内容
     => 要拿到内容, 只能: ① 用 cmd 0x1B 从设备读回  ② 找到单独的 cfg/nvram 文件

  3) ★★★ 关于"只写 0x1800 单字节"的风险 —— 见 ROUND60 报告

"""
import glob
D = open(glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)[0], "rb").read()

print("=== 向量表 (file 0x19ABC) 表项 -> 运行地址 ===")
import struct
VT = 0x19ABC
names = ["SP","Reset","NMI","HardFault","-","-","-","-","-","-","-","SVC","-","-","PendSV","SysTick"]
for i in range(16):
    v = struct.unpack_from("<I", D, VT+i*4)[0]
    tag = ""
    if i == 0: tag = f"  (SP)"
    elif 0x08000000 <= v < 0x0802775C:
        f = v - 0x08000000
        seg = "加密区(0x1000-0x18FFF)" if 0x1000 <= f < 0x19000 else ("明文区(0x19000+)" if f >= 0x19000 else "头部(0-0xFFF)")
        tag = f"  -> file 0x{f:05X}  [{seg}]"
    print(f"  [{i:2d}] {names[i]:<10} 0x{v:08X}{tag}")

print("\n=== 0x08000000..0x0800FFFF 段: 哪些地址被向量表引用 ===")
refs = set()
for i in range(1, 16):
    v = struct.unpack_from("<I", D, VT+i*4)[0]
    if 0x08000000 <= v < 0x0802775C:
        refs.add(v & ~1)
print(f"  引用 {len(refs)} 个地址, 范围 {hex(min(refs))}..{hex(max(refs))}")
print("  => 最大 0x%08X, 落在 %s" % (max(refs), "加密区" if max(refs)-0x08000000 < 0x19000 else "明文区"))
