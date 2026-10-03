# -*- coding: utf-8 -*-
"""C03. ★ 决定性实验: 1024 周期信号是否 *完全* 来自重复数据表?
方法: 把已知重复表(0x3800,0x5800,0x8800..0x9800,0xF800 等)整块挖掉后, 重测 1024 周期。
若挖掉后 1024 周期匹配率跌回随机水平 => 结论 C('无加扰')成立, 且原分析者的
'4 份零差异 1024B 表' 正是造成假周期信号的唯一原因。
若仍有残留 => 存在真实的 1KiB 周期结构, 结论 C 需要修正。
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW)

def match_rate_idx(pairs_mask, L):
    c = 0; t = 0
    for i in pairs_mask:
        if 0 <= i and i + L < N:
            if FW[i] == FW[i+L]: c += 1
            t += 1
    return c/t if t else 0

print("=" * 96)
print("C03-a. 找出所有 512B 高熵'表块', 用 4 份零差异表做种子")
print("=" * 96)
# 用 512B 块做指纹(step 512)，找重复
from collections import defaultdict
d = defaultdict(list)
for o in range(0, N-512+1, 512):
    d[FW[o:o+512]].append(o)
dups = {k: v for k, v in d.items() if len(v) > 1}
print(f"  512B 对齐块的总数 = {(N)//512}")
print(f"  重复的 512B 块种类 = {len(dups)}")
tab_ranges = []
for k, v in sorted(dups.items(), key=lambda x: x[1][0]):
    print(f"    x{len(v):>2d}  @ {[hex(x) for x in v]}  熵={entropy(k):.4f}")
    for x in v:
        tab_ranges.append((x, x+512))
# 合并相邻
tab_ranges.sort()
merged = []
for a, b in tab_ranges:
    if merged and a <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], b)
    else: merged.append([a, b])
print(f"  合并后的重复表区段 = {[(hex(a),hex(b)) for a,b in merged]}")
tab_total = sum(b-a for a,b in merged)
print(f"  重复表总字节 = {tab_total}")

print("\n" + "=" * 96)
print("C03-b. ★ 挖掉重复表后重测 1024 周期 (对照: 挖掉前)")
print("=" * 96)
def masked_rate(L, exclude):
    c = 0; t = 0
    for i in range(0x01200, 0x19000, 7):   # 步长 7 避免与 1024 网格对齐
        inj = any(a <= i < b or a <= i+L < b for a, b in exclude)
        if inj: continue
        if i + L >= N: continue
        if FW[i] == FW[i+L]: c += 1
        t += 1
    return c, t, (c/t if t else 0)

for L in (256, 1024, 2048, 4096, 8192):
    c0, t0, r0 = masked_rate(L, [])
    cm, tm, rm = masked_rate(L, [(a, b) for a, b in merged])
    print(f"  L={L:>5d}  挖表前 {r0:.5f} ({c0}/{t0})   挖表后 {rm:.5f} ({cm}/{tm})"
          f"   降幅 {r0/rm if rm else 0:.2f}x  {'<<< 周期信号来自重复表' if rm < 0.01 else ''}")

print("\n" + "=" * 96)
print("C03-c. ★ 用 1KiB 网格严格测: 挖掉重复表, 相邻 1KiB 块完全相同? ")
print("=" * 96)
print("  对比 1KiB 块 A 与 A+0x1000 的完整相同块数 (挖掉表区)")
cnt_eq = 0; cnt_tot = 0
for o in range(0x01200, 0x19000 - 0x1000, 0x1000):
    inj = any(a <= o < b or a <= o+0x1000 < b for a, b in merged)
    if inj: continue
    cnt_tot += 1
    if FW[o:o+0x1000] == FW[o+0x1000:o+0x2000]: cnt_eq += 1
print(f"  1KiB 块对总数={cnt_tot}  完全相同的对={cnt_eq}")

print("\n" + "=" * 96)
print("C03-d. ★ 4 份零差异 1024B 表 精确定位与内容性质")
print("=" * 96)
t0 = FW[0x8800:0x8C00]
# 注意 0x8800/0x8C00/0x9000/0x9400 是 4 份 512B 的交替, 合起来要看 0x8800-0x9800
blk = FW[0x8800:0x9800]
print(f"  0x8800-0x9800 共 {len(blk)} B")
for i in range(0, 0x1000, 512):
    print(f"    @0x{0x8800+i:05X} 熵={entropy(FW[0x8800+i:0x8800+i+512]):.4f} "
          f"前16B={' '.join(f'{b:02x}' for b in FW[0x8800+i:0x8800+i+16])}")
# 与 0x8600 / 0x8A00 对比 (奇偶交替?)
print(f"\n  0x8600 前16B = {' '.join(f'{b:02x}' for b in FW[0x8600:0x8610])}")
print(f"  0x8800 前16B = {' '.join(f'{b:02x}' for b in FW[0x8800:0x8810])}")
print(f"  0x8C00 前16B = {' '.join(f'{b:02x}' for b in FW[0x8C00:0x8C10])}")
print(f"  0x8E00 前16B = {' '.join(f'{b:02x}' for b in FW[0x8E00:0x8E10])}")
# 检查 0x8800 表是否 = 0x8600 表 的某种变换
a = FW[0x8600:0x8800]; b = FW[0x8800:0x8A00]
print(f"\n  0x8600 与 0x8800 的 512B 是否相同? {a==b}")
print(f"  逐字节 XOR 唯一值数 = {len(set(x^y for x,y in zip(a,b)))}")
print(f"  逐字节 XOR 前16 = {' '.join(f'{x^y:02x}' for x,y in list(zip(a,b))[:16])}")
