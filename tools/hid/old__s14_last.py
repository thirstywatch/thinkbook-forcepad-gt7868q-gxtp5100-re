"""步骤14：最后三问
(a) GPIO 基址点后调用的 helper 全集
(b) DMA：包含 0x0800F470 的函数及其调用者（是否有 DMA 基址作为实参）
(c) USART1 驱动（0x0800DD40 一带）的调用者与用途
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

ASM = os.path.join(ROOT, "touchpad_TF100A_thumb.asm.txt")
rows = []
for l in open(ASM, encoding="utf-8"):
    p = l.rstrip().split(None, 2)
    if len(p) < 2:
        continue
    try:
        pc = int(p[0], 16)
    except ValueError:
        continue
    rows.append((pc, p[1], p[2] if len(p) > 2 else ""))
IDX = {r[0]: k for k, r in enumerate(rows)}
CAL = collections.defaultdict(list)
for pc, mn, ops in rows:
    if mn in ("bl", "blx", "b.w") and ops.startswith("#"):
        CAL[int(ops[1:], 16)].append(pc)

print("=== (a) GPIO 基址点之后 12 条内的 bl 目标 ===")
gpio_sites = []
for k, (pc, mn, ops) in enumerate(rows):
    if mn == "movw" and ops in ("r0, #0x800", "r0, #0xc00", "r0, #0x1000", "r0, #0x1400", "r0, #0x1800", "r5, #0xc00"):
        # 检查下一条 movt 是否为 0x4001
        if k + 1 < len(rows) and rows[k + 1][1] == "movt" and rows[k + 1][2] in ("r0, #0x4001", "r5, #0x4001"):
            gpio_sites.append(pc)
tgts = collections.Counter()
for pc in gpio_sites:
    k = IDX[pc]
    for j in range(k, min(len(rows), k + 14)):
        a, mn, ops = rows[j]
        if mn in ("bl", "blx", "b.w") and ops.startswith("#"):
            tgts[ops] += 1
for t, c in tgts.most_common():
    print("   %s x%d" % (t, c))
print("   GPIO 基址点 %d 个" % len(gpio_sites))

print("\n=== (b) 包含 0x0800F470 的函数 ===")
k = IDX[0x0800F470]
s = k
while s > 0:
    a, mn, ops = rows[s]
    if mn == "push" and "lr" in ops:
        break
    s -= 1
print("  函数起点 0x%08X" % rows[s][0])
for j in range(s, min(len(rows), s + 40)):
    print("    0x%08X  %-8s %s" % rows[j])
st = rows[s][0]
print("  该函数的调用者: %s" % (CAL.get(st, "无")))

print("\n=== (c) USART1 相关函数的调用者 ===")
for t in (0x0800DD40 & ~1,):
    pass
# 找 0x0800DD40 所在函数起点
k = IDX[0x0800DD40]
s = k
while s > 0:
    a, mn, ops = rows[s]
    if mn == "push" and "lr" in ops:
        break
    s -= 1
print("  0x0800DD40 所在函数起点 0x%08X" % rows[s][0])
for j in range(s, min(len(rows), s + 60)):
    print("    0x%08X  %-8s %s" % rows[j])
print("  调用者: %s" % CAL.get(rows[s][0], "无"))
for t in (0x0800DD74, 0x0800DD64):
    for pc, mn, ops in rows:
        if mn in ("bl", "blx", "b.w") and ops == "#0x%x" % t:
            print("  0x%08X -> 0x%08X 调用者函数链" % (pc, t))
