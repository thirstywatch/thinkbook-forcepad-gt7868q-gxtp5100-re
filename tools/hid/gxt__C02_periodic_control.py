# -*- coding: utf-8 -*-
"""C02. ★ 修正 C01-c 的判据失效问题。
C01-c 在 L=16 也报 z=96 -> 判据失效。原因: 
  (1) 白化区不是均匀 i.i.d. 随机(有真实数据表、低熵窗口)；
  (2) 采样区间覆盖了重复表区域, 人为拉高了匹配率；
  (3) 更根本: FW[i]==FW[i+L] 的匹配率对"任何"有轻微偏斜的流都会高, 不能当周期性判据。
正确做法: 与同长度的 *打乱版本(shuffle)* 对照 —— 若无周期, 匹配率应等于 shuffle 版。
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW)

def match_rate(buf, L, limit):
    c = 0; t = 0
    for i in range(min(len(buf) - L, limit)):
        if buf[i] == buf[i+L]: c += 1
        t += 1
    return c/t if t else 0

print("=" * 96)
print("C02-a. ★ 对照实验: 真实白化区 vs 同长度 shuffle vs 纯随机")
print("=" * 96)
print("  取 0x01200-0x19000 中一段 *不含重复表* 的 48 KiB: 0x04000-0x10000")
REG = FW[0x04000:0x10000]
rng = random.Random(99)
shuf = bytearray(REG); rng.shuffle(shuf); shuf = bytes(shuf)
pure = bytes(rng.randrange(256) for _ in range(len(REG)))
print(f"  测试区长度 = {len(REG)} = 0x{len(REG):X}")
print(f"  {'L':>7} {'真实匹配率':>12} {'shuffle':>10} {'纯随机':>10}  {'真实/shuffle比':>14}")
for L in (16, 64, 256, 1024, 2048, 4096, 8192, 16384):
    a = match_rate(REG, L, 20000)
    b = match_rate(shuf, L, 20000)
    c = match_rate(pure, L, 20000)
    ratio = a/b if b else 0
    print(f"  {L:>7d} {a:>12.5f} {b:>10.5f} {c:>10.5f}  {ratio:>14.3f}"
          + ("   <<< 真实显著高于对照" if ratio > 2 else ""))

print("\n" + "=" * 96)
print("C02-b. ★ 专用检验: 只查 1024 周期在 *非重复表区* 是否成立")
print("=" * 96)
print("  逐 1KiB 块与它后 1KiB 块的字节相同率 (只统计 0x04000-0x18000, 跳过 0x8800 表)")
for base in range(0x04000, 0x18000, 0x4000):
    eq = 0; tot = 0
    for i in range(base, base + 0x4000):
        if i + 0x1000 >= N: break
        if 0x8800 <= i < 0x8C00 or 0x8800 <= i+0x1000 < 0x8C00: continue
        if 0x8c00 <= i < 0x9000 or 0x8c00 <= i+0x1000 < 0x9000: continue
        if 0x9000 <= i < 0x9400 or 0x9000 <= i+0x1000 < 0x9400: continue
        if FW[i] == FW[i+0x1000]: eq += 1
        tot += 1
    print(f"    起点 0x{base:05X}: 相同字节 {eq}/{tot} = {eq/tot:.5f}  (随机=0.00391)")

print("\n" + "=" * 96)
print("C02-c. ★ 分区间熵: 10 个子分区各自独立统计 (结论 C 第 4 点)")
print("=" * 96)
# 用 A7 得到的真实分区: type=0x02 的是代码/数据区, type=0x03 是白化区(每 0x20000)
parts = [(0x00000, 0x10000, 0x02), (0x10000, 0x40000, 0x02), (0x40000, 0x60000, 0x03),
         (0x60000, 0x80000, 0x03), (0x80000, 0xA0000, 0x03), (0xA0000, 0xC0000, 0x03),
         (0xC0000, 0xE0000, 0x03), (0xE0000, 0x100000, None),  # 空隙
         (0x100000, 0x120000, 0x03), (0x120000, 0x130000, 0x02),
         (0x130000, 0x160000, 0x02), (0x160000, 0x180000, 0x03),
         (0x180000, 0x1E0000, None), (0x1E0000, 0x200000, 0x03)]
print(f"  {'区间':>22} {'type':>6} {'文件内?':>8} {'熵':>8} {'chi2':>8} {'零占比':>8}")
for a, b, t in parts:
    if a >= N:
        print(f"  [{a:#09x},{b:#09x}) {str(t):>6} {'超出文件':>8}    --       --       --")
        continue
    sub = FW[a:min(b, N)]
    print(f"  [{a:#09x},{b:#09x}) {('0x%02X'%t) if t else '  空':>6} "
          f"{('部分 %d B'%len(sub)):>8} {entropy(sub):>8.4f} {chi2_uniform(sub):>8.1f} "
          f"{sub.count(0)/len(sub):>8.4f}")

print("\n" + "=" * 96)
print("C02-d. ★ 高熵'整齐块'定位: 熵 > 7.7 的 512B 窗口 (重复表候选)")
print("=" * 96)
for off in range(0x01200, 0x19000, 512):
    e = entropy(FW[off:off+512])
    if e > 7.70:
        print(f"    0x{off:05X} 熵={e:.4f}")
