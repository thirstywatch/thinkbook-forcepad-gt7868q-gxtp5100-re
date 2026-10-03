# -*- coding: utf-8 -*-
"""F01. ★ 向量表搜索 (强判据) + 基址关系 + 代码/数据分段图。
强判据: Cortex-M 向量表前两项 = [初始SP, 复位向量(奇数)]，且后续项应是
        连续的非零代码地址(奇数)。
先标定: 人造向量表; 再上真实数据。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW)

def vec_score(off, base, limit=48):
    """score = 连续'奇数且落在 [base, base+size)'的项数"""
    good = 0
    for i in range(limit):
        o = off + i*4
        if o+4 > N: break
        v = le32(FW, o)
        if v == 0: continue
        if (v & 1) and base <= v < base + 0x400000:
            good += 1
    return good

print("=" * 96)
print("F01-a. 向量表强判据扫描 (base = flash 别名 0x08000000, 以及 0x00000000)")
print("=" * 96)
print("  标定: 人造向量表(全部奇数且在区内) 应得满分")
# 人造: 在 0x1000 造一张向量表
import random
rng = random.Random(3)
test = bytearray(FW[:0x2000])
test[0x1000:0x1000+4] = (0x20001000).to_bytes(4, "little")
for i in range(1, 48):
    test[0x1000+i*4:0x1000+i*4+4] = (0x08001001 + i*8).to_bytes(4, "little")
FWbk = FW
FW = bytes(test)
print(f"  人造表@0x1000 score(0x08000000) = {vec_score(0x1000, 0x08000000)}")
print(f"  随机位置 0x1100 score = {vec_score(0x1100, 0x08000000)}")
FW = FWbk

best = []
for off in range(0, N - 200, 4):
    s1 = vec_score(off, 0x08000000)
    s2 = vec_score(off, 0x00000000)
    if s1 >= 20 or s2 >= 20:
        sp = le32(FW, off)
        best.append((off, s1, s2, sp))
print(f"\n  真实固件中 score>=20 的候选 = {len(best)}")
for off, s1, s2, sp in best[:40]:
    print(f"    @0x{off:05X} score_flash={s1:>3d} score_low={s2:>3d} SP=0x{sp:08X}")

print("\n" + "=" * 96)
print("F01-b. ★ 候选向量表的 SP 值分布 (SP 应集中在 RAM 区小范围)")
print("=" * 96)
print("  注: 固件从 0x19850 起是真 Thumb 代码, 若其为裸机固件, 向量表应在它之前的部分。")
print("  检查 0x19850 之前的 0x19800-0x19850:")
for o in range(0x19800, 0x19860, 16):
    print(f"    0x{o:05X}  {' '.join(f'{b:02x}' for b in FW[o:o+16])}")

print("\n" + "=" * 96)
print("F01-c. ★★ 基址关系推断: 用 BL 目标 + 绝对地址立即数反推代码基址")
print("=" * 96)
from capstone import *
from capstone.arm import *
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True
# 在 0x19850-0x26500 收集 ldr [pc,#imm] 与 movw/movt 的立即数
imms = []
for i in range(0x19850, 0x26500, 2):
    for ins in md.disasm(FW[i:i+4], i):
        if ins.size > 4: break
        for op in ins.operands:
            if op.type == ARM_OP_IMM:
                imms.append((i, ins.mnemonic, op.imm))
        break
from collections import Counter
c = Counter()
for _, m, v in imms:
    c[v & 0xFFF00000] += 1       # 高位页
print("  立即数高位页 (top 15):")
for k, v in c.most_common(15):
    print(f"    页 0x{k:08X}xxxx : {v} 次")
print("\n  立即数中落在已知地址族:")
fam = Counter()
for _, m, v in imms:
    if 0x40000000 <= v < 0x60000000: fam["外设 0x40000000"] += 1
    elif 0x20000000 <= v < 0x20080000: fam["RAM 0x20000000"] += 1
    elif 0x08000000 <= v < 0x08200000: fam["FLASH 0x08000000"] += 1
    elif v < 0x00030000: fam["低线性 <0x30000"] += 1
print(f"    {dict(fam)}")
print("\n  低线性区立即数 top20 (可反推文件偏移基址):")
cl = Counter(v for _, m, v in imms if v < 0x30000)
for k, v in cl.most_common(20):
    print(f"    0x{k:05X} : {v} 次")
