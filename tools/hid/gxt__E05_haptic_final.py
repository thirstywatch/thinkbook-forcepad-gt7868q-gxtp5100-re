# -*- coding: utf-8 -*-
"""E05. ★★ 触觉最终排查:
  1. AW86927 的 I2C 地址 0x5A/0x5B 是否在代码区作为立即数写入
  2. AW86927 寄存器 (0x00-0x7F) 的写序列模式
  3. 用 capstone 找所有 'constant + offset store' 的外设写
  4. 检查 0x1E000-0x20000 配置区的 [reg][val] 记录
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
from collections import Counter
FW = load(); N = len(FW)
CODE_LO, CODE_HI = 0x19850, 0x265B8
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True

print("=" * 100)
print("E05-a. ★ 代码区: movs rX,#imm / mov.w 立即数 0x5A/0x5B 的上下文")
print("=" * 100)
for i in range(CODE_LO, CODE_HI, 2):
    for ins in md.disasm(FW[i:i+4], i):
        if ins.size > 4: break
        if ins.mnemonic in ("movs", "mov", "mov.w", "movw"):
            m = re.search(r"#(0x[0-9a-fA-F]+|\d+)", ins.op_str)
            if m:
                v = int(m.group(1), 0)
                if v in (0x5A, 0x5B, 0x2D, 0xB4, 0xB5, 0x01D4, 0x1D4):
                    # 打印前后 6 条上下文
                    print(f"  --- imm=0x{v:X} @0x{i:05X} ---")
                    base = max(CODE_LO, i-12)
                    for ins2 in md.disasm(FW[base:base+32], base):
                        mk = " <<<" if ins2.address == i else ""
                        print(f"      0x{ins2.address:05X}  {ins2.mnemonic:<9s} {ins2.op_str}{mk}")
        break

print("\n" + "=" * 100)
print("E05-b. ★★ 代码区所有 'str rX,[rY,#imm]' 且 imm 落在 0x00-0x1FF 的写操作 (寄存器写入模式)")
print("=" * 100)
# 找 str rX, [rY, #imm] 和 strb，imm 是寄存器偏移 -> 说明有基址寄存器(外设)
writes = Counter()
samples = {}
for i in range(CODE_LO, CODE_HI, 2):
    for ins in md.disasm(FW[i:i+4], i):
        if ins.size > 4: break
        if ins.mnemonic in ("str", "strh", "strb") and len(ins.operands) == 2 \
           and ins.operands[1].type == ARM_OP_MEM and ins.operands[1].mem.disp > 0 \
           and ins.operands[1].mem.base != ARM_REG_PC and ins.operands[1].mem.base != ARM_REG_SP:
            writes[ins.operands[1].mem.disp] += 1
            samples.setdefault(ins.operands[1].mem.disp, []).append((i, ins.mnemonic, ins.op_str))
        break
print(f"  不同寄存器偏移数 = {len(writes)}")
print("  Top 25 偏移 (可能是外设寄存器偏移):")
for d, n in writes.most_common(25):
    ex = samples[d][0]
    print(f"    offset 0x{d:03X}: {n:>4d} 次   例如 @0x{ex[0]:05X}: {ex[1]} {ex[2]}")

print("\n" + "=" * 100)
print("E05-c. ★★ 0x1E000-0x20000 配置区: 找 [reg][val] 对 / 索引表")
print("=" * 100)
sub = FW[0x1E000:0x20000]
print(f"  长度 {len(sub)} 熵={entropy(sub):.4f}")
# 检查是否含规律序列
# 1) 找 2 字节步长的 (a,b) 模式
pairs = Counter()
for i in range(0, len(sub)-1, 2):
    pairs[(sub[i], sub[i+1])] += 1
print(f"  2 字节对总数 {len(pairs)}  最常见:")
for (a, b), n in pairs.most_common(15):
    print(f"    ({a:02x},{b:02x}) x{n}")
# 2) 检查偏置
print("\n  单字节分布 top15:", [(f"{k:02x}", v) for k, v in Counter(sub).most_common(15)])
# 3) 按 16 字节块看结构
print("\n  0x1E000 起 128 字节:")
for o in range(0, 128, 16):
    print(f"    0x{0x1E000+o:05X}  {' '.join(f'{b:02x}' for b in sub[o:o+16])}")

print("\n" + "=" * 100)
print("E05-d. ★★ 检查是否有 AW86927 特有的寄存器值模式 (0x00-0x7F reg, 写序列)")
print("=" * 100)
# AW86927 常见初始化: 写 0x0000-0x00FF 范围内的寄存器, 值多为小整数
# 找 'ldr rX,[pc,#imm]' 加载的常量里, 是否有 < 0x100 的值(寄存器地址) 与 0x4000xxxx 一起
print("  (无外设基址 => 无法定位寄存器基址, 见 E04)")

print("\n" + "=" * 100)
print("E05-e. ★★★ 触觉关键词的'变形'搜索 (16-bit 字节交换 / 二进制模式)")
print("=" * 100)
kws = [b"AW869", b"86927", b"awinic", b"AWINIC", b"LRA", b"HAPTIC", b"haptic",
       b"VIBR", b"vibr", b"BEMF", b"motor", b"TRIG", b"WAVE", b"GT7868", b"GT7868Q"]
for kw in kws:
    # 原样
    n0 = FW.count(kw)
    # 大小写全变体
    variants = {kw, kw.lower(), kw.upper(), kw.capitalize()}
    tot = sum(FW.count(v) for v in variants)
    # 字符间插 0 (有些固件字符串是 UTF-16LE)
    utf16 = b"".join(bytes([c, 0]) for c in kw)
    n16 = FW.count(utf16)
    utf16b = b"".join(bytes([0, c]) for c in kw)
    n16b = FW.count(utf16b)
    if tot or n16 or n16b:
        print(f"  {kw!r}: 原样/大小写={tot} UTF16LE={n16} UTF16BE={n16b}")
print("  (只打印非零项)")
