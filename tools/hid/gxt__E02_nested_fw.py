# -*- coding: utf-8 -*-
"""E02. ★★ 重大发现追查: 0x19ECC "TF100A_Test_FW" + 构建时间戳。
这看起来是"嵌套的第二个固件镜像"(任务 F4)。验证:
  1. 0x19ECC 前后的字符串群 (版本块)
  2. 该块之前的 ARM 代码是否是一个独立的固件入口 (向量表?)
  3. 是否还有其它 "xxx_FW" / 版本块
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW)

print("=" * 96)
print("E02-a. 0x19E00-0x19F80 全貌 (版本块 + 代码)")
print("=" * 96)
for o in range(0x19DF0, 0x19F90, 16):
    print(f"  0x{o:05X}  {' '.join(f'{b:02x}' for b in FW[o:o+16])}"
          f"  |{''.join(chr(b) if 32<=b<127 else '.' for b in FW[o:o+16])}|")

print("\n" + "=" * 96)
print("E02-b. ★ 全文件 'xxx_FW' / 版本字符串 / 日期 模式搜索")
print("=" * 96)
for pat in [rb"[\x20-\x7e]{4,}_FW", rb"[A-Z][A-Z0-9]{2,}[0-9]{2,}[A-Z]?",
            rb"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [ \d]\d \d{4}",
            rb"\d\d:\d\d:\d\d", rb"GT\d{4}", rb"[A-Z0-9]{4,}_(FW|fw|Test|test|Ver|ver)[\w]*"]:
    print(f"  模式 {pat}:")
    for m in re.finditer(pat, FW):
        s = m.group().decode("ascii", "replace")
        print(f"    0x{m.start():05X}  {s!r}")

print("\n" + "=" * 96)
print("E02-c. ★ 0x19ECC 之前的代码: 是否为独立固件(有自己的向量表/入口)?")
print("=" * 96)
# 往前找可能向量表: 在 0x19850 - 0x19ECC 之间找 SP/Reset 对
for off in range(0x19700, 0x19ED0, 4):
    a = le32(FW, off); b = le32(FW, off+4)
    if 0x20000000 <= a < 0x20080000 and (b & 1) and 0x1000 <= b < 0x200000:
        print(f"  候选向量表 @0x{off:05X}: SP=0x{a:08X} Reset=0x{b:08X}")
    # 也接受 0x08000000 flash
    if 0x08000000 <= a < 0x08100000 and (b & 1) and 0x08000000 <= b < 0x08100000:
        print(f"  候选向量表 @0x{off:05X}: SP=0x{a:08X} Reset=0x{b:08X} (flash 别名)")

print("\n" + "=" * 96)
print("E02-d. ★ 反向检查: 版本块附近是否有 'magic' 结构 (firmware header)")
print("=" * 96)
print("  0x19ECC 前 64 B, 按 u32 LE 解读:")
for o in range(0x19E8C, 0x19ED0, 4):
    print(f"    0x{o:05X}  {le32(FW,o):#010x}  {be32(FW,o):#010x} (BE)")

print("\n" + "=" * 96)
print("E02-e. ★ 检查是否有第二个 'TF100' 或压力相关块: 搜索 'AP' 'Pres' 'P1' 等")
print("=" * 96)
print("  0x19E80 处的 00 41 50 ea = ?  (0xea 50 41 00 LE = 0xea504100)")
print(f"  le32@0x19E82 = {le32(FW,0x19E82):#010x}")
print(f"  le32@0x19E86 = {le32(FW,0x19E86):#010x}")
print("  提示: 0x19E80 前是 '00 20 70 47' = movs r0,#0 / bx lr (函数返回)")
