# -*- coding: utf-8 -*-
"""F02. ★★ 分段图 + 文件偏移<->flash地址映射。
已知事实:
  - 0x19850 起是真 Thumb-2 代码 (非法率 0.000), 直到 ~0x265C0
  - 0x265C0 之后非法率回升 (0.03-0.09) => 又变回数据/白化
  - 0x19800 之前 (含 0x19800-0x19850) 是白化/表格数据
  - 分区表声明整个镜像应是 0x200000 (2 MB), 文件只有 0x2775C (158 KB)
任务: 给出文件内每一段的性质表 + 猜测 flash 地址映射
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
FW = load(); N = len(FW)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

def badrate(off, ln):
    i = off; ok = 0; bad = 0
    while i < min(off+ln, N):
        got = None
        for ins in md.disasm(FW[i:i+16], i):
            got = ins; break
        if got is None: bad += 1; i += 2; continue
        ok += 1; i += got.size
    return bad/(ok+bad) if ok+bad else 1.0

print("=" * 100)
print("F02-a. ★ 全长分段扫描 (1 KiB 窗口, 判据=非法率)")
print("=" * 100)
print(f"  {'offset':>9} {'非法率':>8} {'熵':>7} {'零占比':>7}  {'类别':<14} 条")
segs = []
for off in range(0, N, 0x1000):
    ln = min(0x1000, N-off)
    br = badrate(off, ln)
    e = entropy(FW[off:off+ln])
    z = FW[off:off+ln].count(0)/ln
    if off < 0x1164:
        cat = "表/配置"
    elif off < 0x1200:
        cat = "分区表"
    elif off < 0x19850:
        cat = "白化/高熵数据"
    elif off < 0x26600:
        cat = "★★ ARM Thumb-2 代码"
    else:
        cat = "数据/白化"
    bar = "#" * int(br*50)
    print(f"  0x{off:07X} {br:8.4f} {e:7.4f} {z:7.4f}  {cat:<14} {bar}")
    segs.append((off, ln, br, e, cat))

print("\n" + "=" * 100)
print("F02-b. ★ 精确定位所有类别跃变点")
print("=" * 100)
prev = None
for off, ln, br, e, cat in segs:
    if prev != cat:
        print(f"    0x{off:05X}  ->  {cat}")
        prev = cat

print("\n" + "=" * 100)
print("F02-c. ★★ 代码段精确边界 (逐 16B 细扫跃变点)")
print("=" * 100)
def find_transition(lo, hi, step, thr=0.02):
    prev = None
    for off in range(lo, hi, step):
        br = badrate(off, 32)
        cur = br > thr
        if prev is not None and cur != prev:
            print(f"    @0x{off:05X}: 非法率 {br:.4f}  转变 {'-> 差' if cur else '-> 好'}")
        prev = cur
print("  0x19700-0x19A00 (代码起点):")
find_transition(0x19700, 0x19A00, 16)
print("  0x26400-0x26800 (代码终点):")
find_transition(0x26400, 0x26800, 16)

print("\n" + "=" * 100)
print("F02-d. ★★ 文件偏移 -> flash 地址 假设检验")
print("=" * 100)
print("  假设 H1: 文件 = flash 偏移 0..0x2775C (基址 0x08000000 -> 地址 0x08000000+off)")
print("  假设 H2: 文件是某个分区的内容, 该分区 flash 起始 = 0x130000 (type=0x02, size=0x30000)")
print("           -> 文件长 0x2775C < 0x30000 且 > 0x20000")
print()
# H2: 若代码段在文件 0x19850, 则 flash 地址 = 0x130000 + 0x19850 = 0x149850
print(f"  H2 下代码段起址 = 0x130000 + 0x19850 = 0x{0x130000+0x19850:06X}")
print(f"  H2 下文件尾地址 = 0x130000 + 0x{N:X} = 0x{0x130000+N:06X}  (分区尾 0x160000)")
print(f"  分区 0x130000-0x160000 长 0x30000={0x30000}; 文件 {N}=0x{N:X}; 差 {0x30000-N}")
print()
# 关键: 检查代码里的 bl 目标是否落在 H2 假设的地址空间
print("  检验: 收集 0x19850-0x26500 的 BL 目标(相对), 看绝对地址落在哪")
base_h1 = 0x08000000
base_h2 = 0x130000
for name, base in [("H1 base=0x08000000", 0x08000000), ("H2 base=0x00130000", 0x00130000),
                   ("H2b base=0x00000000", 0x00000000)]:
    tgts = []
    for i in range(0x19850, 0x26500, 2):
        for ins in md.disasm(FW[i:i+4], base + i):
            if ins.size > 4: break
            if ins.mnemonic in ("bl", "b.w"):
                for op in ins.operands:
                    if op.type == 1:  # ARM_OP_IMM
                        tgts.append(op.imm)
            break
    lo = min(tgts) if tgts else 0; hi = max(tgts) if tgts else 0
    inzone = sum(1 for t in tgts if base <= t < base + N)
    print(f"    {name:22s} BL数={len(tgts):>4d} 范围=[0x{lo:08X},0x{hi:08X}] "
          f"落在文件映射区={inzone}/{len(tgts)}")
