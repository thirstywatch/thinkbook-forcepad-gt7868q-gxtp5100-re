# -*- coding: utf-8 -*-
"""E04. ★ 真实地址空间识别: 代码区到底访问哪里的寄存器?
若 0x4000xxxx 不存在, 说明:
  (a) 这段代码不是主 MCU 代码, 而是某个协处理器/传感器芯片的固件 (可能通过 SPI 与主 MCU 通信)
  (b) 地址空间是 0x5000xxxx / 0xF0000000 / 或很小 (< 0x10000)
本脚本: 统计代码区/bl 目标/绝对地址常量的真实分布, 推断地址空间。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
from collections import Counter
FW = load(); N = len(FW)
CODE_LO, CODE_HI = 0x19850, 0x265B8
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True

print("=" * 100)
print("E04-a. ★ 代码区所有 PC 相对常量池落点 + 值 (全量列表)")
print("=" * 100)
pool = {}
for i in range(CODE_LO, CODE_HI, 2):
    for ins in md.disasm(FW[i:i+4], i):
        if ins.size > 4: break
        if ins.mnemonic.startswith("ldr") and len(ins.operands) == 2 \
           and ins.operands[1].type == ARM_OP_MEM and ins.operands[1].mem.base == ARM_REG_PC:
            tgt = i + 4 + ins.operands[1].mem.disp
            if 0 <= tgt < N-4:
                pool.setdefault(tgt, []).append(i)
        break
print(f"  唯一池落点 = {len(pool)}")
vals = {a: le32(FW, a) for a in pool}
hist = Counter()
for v in vals.values():
    if v < 0x10000: hist["0x00000-0x0FFFF (低线性)"] += 1
    elif v < 0x100000: hist["0x10000-0xFFFFF"] += 1
    elif 0x20000000 <= v < 0x20100000: hist["RAM 0x2000xxxx"] += 1
    elif 0x40000000 <= v < 0x40100000: hist["外设 0x4000xxxx"] += 1
    elif 0x48000000 <= v < 0x48100000: hist["外设 0x4800xxxx"] += 1
    elif 0x08000000 <= v < 0x09000000: hist["FLASH 0x0800xxxx"] += 1
    elif v >= 0xE0000000: hist["系统 0xExxxxxxx"] += 1
    elif v == 0: hist["0"] += 1
    else: hist["其它"] += 1
print(f"  {dict(hist)}")
print("\n  全部池值 (字母序):")
for a in sorted(vals):
    print(f"    @0x{a:05X} = 0x{vals[a]:08X}   被引用于 {[hex(x) for x in pool[a]]}")

print("\n" + "=" * 100)
print("E04-b. ★★ 代码区的 BL/B 目标分布 (推断代码地址基址)")
print("=" * 100)
tgts = Counter()
for i in range(CODE_LO, CODE_HI, 2):
    for ins in md.disasm(FW[i:i+4], i):
        if ins.size > 4: break
        if ins.mnemonic in ("bl", "b.w", "b") and ins.operands:
            if ins.operands[0].type == ARM_OP_IMM:
                t = ins.operands[0].imm
                tgts[t - i] += 1      # 相对位移
        break
print("  最常见相对位移 (BL/B):")
for d, n in tgts.most_common(20):
    print(f"    d={d:>+8d} (0x{d & 0xFFFFFFFF:08X})  x{n}")

print("\n" + "=" * 100)
print("E04-c. ★★ 反汇编 0x19850-0x19950 (代码入口) 看启动流程")
print("=" * 100)
for ins in md.disasm(FW[0x19850:0x19950], 0x19850):
    print(f"    0x{ins.address:05X}  {ins.mnemonic:<8s} {ins.op_str}")

print("\n" + "=" * 100)
print("E04-d. ★★★ 全代码区扫描 movw/movt 构造的 32-bit 常量")
print("=" * 100)
consts = Counter()
i = CODE_LO
while i < CODE_HI:
    got = None
    for ins in md.disasm(FW[i:i+4], i):
        got = ins; break
    if got is None:
        i += 2; continue
    if got.mnemonic in ("movw", "mov") and got.op_str.startswith("r") and "#" in got.op_str:
        # 尝试配对下一条 movt
        j = i + got.size
        got2 = None
        for ins2 in md.disasm(FW[j:j+4], j):
            got2 = ins2; break
        if got2 and got2.mnemonic == "movt":
            # 提取两个立即数
            import re
            a = re.search(r"#(0x[0-9a-f]+|\d+)", got.op_str)
            b = re.search(r"#(0x[0-9a-f]+|\d+)", got2.op_str)
            if a and b:
                lo = int(a.group(1), 0) & 0xFFFF
                hi = int(b.group(1), 0) & 0xFFFF
                v = (hi << 16) | lo
                consts[v] += 1
                if i < 0x19A00: print(f"      @0x{i:05X}: movw/movt -> 0x{v:08X}")
    i += got.size
print(f"\n  找到 {sum(consts.values())} 个 movw/movt 立即数, 唯一值 {len(consts)}")
print("  Top 30 值:")
for v, n in consts.most_common(30):
    print(f"    0x{v:08X}  x{n}")
