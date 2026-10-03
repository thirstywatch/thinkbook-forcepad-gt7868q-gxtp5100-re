#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND52: 完整布局图 + 每个偏移的实际内容
从 round51 的 caller 分析, 还原出 flash 库的相对偏移布局:
  0x03044  1B   (读)
  0x01800  0x1B(27) B  (读 + 写)  <== cmd 0x1B 读 / cmd 0x3200 写
  0x02000  0x444 B     (读, 拷到 0x200044EC)
  0x02444  1B   (读 + 写)
  0x02C00  0x444 B     (读)
  0x03044  1B   (读)
  0x03800  8 B   (读 + 写)       <== cmd 0x1700 写 / 读回 0x2000403C+0xA
  0x00444  1B   (写, src=0x200044EC+0x444)
  0x02444  1B   (写)
  ...
需要注意: 读和写的"长度"参数含义不同吗?
  0x1B874(src, off, len)  len 是 u16
  0x1B7B4(dst, off, len)  len 是 u16
都是 u16, 一致.

关键: 所有这些 off 都 < 0x7000, 所以 0x08019000+off 全在 28KB 区内.
=> 28KB 区 (0x08019000..0x0801FFFF) = "厂商参数区"

但 round49 发现: 该区大部分熵 5.5-6.5 = 像代码!
=> 矛盾. 必须解释: 要么基址不对, 要么 28KB 区就是"代码+数据混排"

决定性检验: 0x08019000 是否是一个"数据区起点"?
  - 若 off=0 处应是某个头/magic
  - 实际看 0x19000: 62 CC 3C 7C 28 EF 8B 3A  -> 不像 magic
  - 但 0x1B7B4 没有 caller 传 off=0

★ 换个思路: 也许基址不是 0x08019000, 而是别的.
  重看 0x1B874:  movw r1,#0x9000 ; movt r1,#0x801 ; add r0,r1
  0x08019000 = 0x08000000 + 0x19000  (file offset 0x19000)
  这是"第2段明文区"的起点 —— 也就是说 flash 库指向"自己所在段的起点"?
  不太可能. 除非... 0x19000 处确实是数据区!

★ 最终裁决手段: 直接看 off=0x444 / 0x1800 / 0x2444 / 0x2C00 / 0x3044 / 0x3800
  这些位置的内容, 判断是"数据"还是"代码"
"""
import os, glob, math, collections

g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
D = open(g[0], "rb").read()
BASE_FILE = 0x19000   # 0x08019000 -> file 0x19000

def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

OFFS = [
    (0x00444, 0x10, "写(byte) src=0x200044EC+0x444"),
    (0x01800, 0x1B, "读+写 27B  <== 主目标"),
    (0x02000, 0x444, "读 0x444B -> RAM 0x200044EC"),
    (0x02444, 0x10, "读+写 单字节"),
    (0x02C00, 0x444, "读 0x444B"),
    (0x03044, 0x10, "读 单字节"),
    (0x03800, 0x10, "读+写 8B   <== 次目标"),
]
print("="*78)
print("flash 库相对偏移 -> 绝对/文件位置 的实际内容")
print("  基址 0x08019000 (= file 0x19000), 全部 off<0x7000 => 全落在 28KB 区内")
print("="*78)
for off, n, desc in OFFS:
    abs_a = 0x08019000 + off
    f = BASE_FILE + off
    print(f"\n--- off 0x{off:04X} -> abs 0x{abs_a:08X} / file 0x{f:X}   [{desc}] ---")
    for r in range(0, n, 16):
        ch = D[f+r:f+r+16]
        if not ch: break
        print(f"    {f+r:06X}  " + " ".join(f"{b:02X}" for b in ch) + "  " +
              "".join(chr(b) if 32<=b<127 else "." for b in ch))

# 检查: 0x19000+0x1800=0x1A800 与 flash 文件里的 "0x1800" 是否有别的解释
print("\n"+"="*78)
print("★ 反向检验: 如果 off 是【绝对地址低16位】, 那 flash 库应指向 0x08000000")
print("  但 movw/movt 给的是 0x08019000. 检查固件里是否还有 0x08000000 基址的 flash 读写模型")
print("="*78)
md = __import__("capstone")
Cs = md.Cs; CS_ARCH_ARM = md.CS_ARCH_ARM; CS_MODE_THUMB=md.CS_MODE_THUMB; CS_MODE_MCLASS=md.CS_MODE_MCLASS
cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB+CS_MODE_MCLASS)

# 扫描 movw+movt 得 0x08000000 或 0x08001000 之类的基址
found = collections.Counter()
for off in range(0x10000, len(D)-3, 2):
    hw1 = int.from_bytes(D[off:off+2],"little"); hw2 = int.from_bytes(D[off+2:off+4],"little")
    if ((hw1>>5)&0x1F) != 0x12: continue
    if ((hw2>>5)&0x1F) != 0x16: continue
    if ((hw1>>8)&0xF) != ((hw2>>8)&0xF): continue
    def imm16(hw): return ((hw>>10)&0x8)|((hw>>12)&0x7)|((hw>>1)&0xF00)
    v = (imm16(hw2)<<16)|imm16(hw1)
    if 0x08000000 <= v < 0x08028000 and (v & 0xFFF) == 0:
        found[v]+=1
print("3KB 对齐的 0x080xxxxx 立即数 (可能是段基址):")
for v,c in sorted(found.items()):
    inrange = " <== off<0x7000 全部落在此段内" if v==0x08019000 else ""
    print(f"  0x{v:08X}  x{c}{inrange}")
