# -*- coding: utf-8 -*-
"""E06. ★★★★ 关键: 追踪 I2C1 (0x40005400) 通信的从地址。
方法: 找所有引用 0x40005400 / 0x40005410 的函数, 打印其完整反汇编,
      人工/自动辨识: 写入 I2C1 DR 的字节值 = 从地址 或 寄存器号。
判据: I2C 从地址写在 DR 的第一字节, 且高7位有效。
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
FW = load(); N = len(FW)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

# 重新收集 movw/movt 常量位置
const_pos = []   # (addr, value)
i = 0x19850
while i < 0x265B8:
    g = None
    for ins in md.disasm(FW[i:i+4], i): g = ins; break
    if g is None: i += 2; continue
    if g.mnemonic == 'movw':
        j = i + g.size
        g2 = None
        for ins2 in md.disasm(FW[j:j+4], j): g2 = ins2; break
        if g2 and g2.mnemonic == 'movt':
            m1 = re.search(r'#(0x[0-9a-f]+|\d+)', g.op_str)
            m2 = re.search(r'#(0x[0-9a-f]+|\d+)', g2.op_str)
            if m1 and m2:
                v = (int(m2.group(1), 0) << 16) | (int(m1.group(1), 0) & 0xFFFF)
                const_pos.append((i, v))
    i += g.size

I2C1 = 0x40005400
tgt = [a for a, v in const_pos if v == I2C1]
print("=" * 104)
print(f"E06-a. 引用 I2C1 基址 (0x{I2C1:08X}) 的代码位置: {[hex(a) for a in tgt]}")
print("=" * 104)

for a in tgt:
    lo = max(0x19850, a - 0x60)
    hi = min(N, a + 0x120)
    print(f"\n--- 上下文 @0x{a:05X} (范围 0x{lo:05X}-0x{hi:05X}) ---")
    for ins in md.disasm(FW[lo:hi], lo):
        mark = " <<<" if ins.address == a else ""
        print(f"    0x{ins.address:05X}  {ins.mnemonic:<10s} {ins.op_str}{mark}")

print("\n" + "=" * 104)
print(f"E06-b. 引用 I2C1 DR (0x40005410) 的位置")
print("=" * 104)
for a, v in const_pos:
    if v == 0x40005410:
        lo, hi = max(0x19850, a-0x50), min(N, a+0x100)
        print(f"\n--- @0x{a:05X} ---")
        for ins in md.disasm(FW[lo:hi], lo):
            mark = " <<<" if ins.address == a else ""
            print(f"    0x{ins.address:05X}  {ins.mnemonic:<10s} {ins.op_str}{mark}")

print("\n" + "=" * 104)
print("E06-c. ★★★ 所有附近的 movs rX,#imm 立即数 (可能是 I2C 从地址 / 寄存器号)")
print("=" * 104)
# 收集 I2C1 引用点前后 0x200 内的 movs 立即数
imm_pool = {}
for a in tgt:
    for i2 in range(max(0x19850, a-0x200), min(N, a+0x200), 2):
        for ins in md.disasm(FW[i2:i+4], i2):
            if ins.size > 4: break
            if ins.mnemonic in ("movs","mov") and "#" in ins.op_str:
                m = re.search(r"#(0x[0-9a-fA-F]+|\d+)", ins.op_str)
                if m:
                    imm_pool.setdefault(int(m.group(1),0), []).append(i2)
            break
print("  出现次数 >= 2 的立即数 (可疑为从地址/寄存器号):")
for v, lst in sorted(imm_pool.items(), key=lambda x: -len(x[1])):
    if len(lst) >= 2 and v < 0x1000:
        tag = ""
        if v in (0x5A, 0x5B): tag = "   <<<<<< AW86927 候选 I2C 地址!!"
        if v == 0x2D: tag = "   <<<<<< 7-bit 0x2D (8-bit 0x5A)"
        print(f"    0x{v:02X} ({v:>3d}) x{len(lst)}  位置 {[hex(x) for x in lst[:6]]}{tag}")
