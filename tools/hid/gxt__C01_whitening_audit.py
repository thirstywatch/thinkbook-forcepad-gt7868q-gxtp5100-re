# -*- coding: utf-8 -*-
"""C01. 加扰存在性复核 —— 逐 512B 熵剖面 + 全周期扫描。
判据标定(随机 512B baseline 由 lib_fw.rand_baseline_line 给出)。
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW)

print("=" * 92)
print("C01-a. 逐 512 B 熵剖面 (0x01200 - 0x19850, 被声称的'白化'区)")
print("=" * 92)
lo, hi = 0x01200, 0x19850
ent_med, chi_med, chi_95 = rand_baseline_line(512, trials=300)
print(f"  随机 512B 基线: 熵中位={ent_med:.4f}  chi2中位={chi_med:.1f}  chi2@95%={chi_95:.1f}")
print(f"  (256 自由度，均匀分布 chi2 期望 255)")
print()
lows = []
for off in range(lo, hi, 512):
    b = FW[off:off+512]
    e = entropy(b); c = chi2_uniform(b); z = b.count(0)/512
    mark = ""
    if e < ent_med - 0.02: mark = " <== 低熵"
    if mark: lows.append((off, e, c, z))
    if off % 2048 == 0 or mark:
        print(f"    0x{off:05X} 熵={e:.4f} chi2={c:8.1f} 零占比={z:.4f}{mark}")
print(f"\n  显著低熵的 512B 窗口数 = {len(lows)}")
for off, e, c, z in lows:
    print(f"    ★ 0x{off:05X} 熵={e:.4f} chi2={c:.1f} 零占比={z:.4f}")

print("\n" + "=" * 92)
print("C01-b. 全区间统计: 0x01200-0x19850 与随机基线的分布对比")
print("=" * 92)
ents = [entropy(FW[o:o+512]) for o in range(lo, hi, 512)]
chis = [chi2_uniform(FW[o:o+512]) for o in range(lo, hi, 512)]
zrs  = [FW[o:o+512].count(0)/512 for o in range(lo, hi, 512)]
import statistics
print(f"  窗口数 = {len(ents)}")
print(f"  熵:   min={min(ents):.4f} max={max(ents):.4f} mean={statistics.mean(ents):.4f} "
      f"stdev={statistics.pstdev(ents):.4f}")
print(f"  chi2: min={min(chis):.1f} max={max(chis):.1f} mean={statistics.mean(chis):.1f}")
print(f"  零占比: min={min(zrs):.4f} max={max(zrs):.4f} mean={statistics.mean(zrs):.4f}")
print(f"  随机基线 熵中位={ent_med:.4f} (本区 mean={statistics.mean(ents):.4f})")
print(f"  -> 差值 = {statistics.mean(ents)-ent_med:+.4f} bits/byte")

print("\n" + "=" * 92)
print("C01-c. ★ 全周期扫描: C[i]==C[i+L] 的匹配率 (不看 1024, 扫 2 的幂与常见值)")
print("=" * 92)
print("  判据: 对偏移 i∈[0, 65536)，统计 FW[i]==FW[i+L] 的比例。")
print("        纯随机 => ~0.0039 (1/256)。周期 L 真实存在 => 显著高于 0.0039。")
for L in (16, 32, 64, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048, 3072, 4096,
          6144, 8192, 12288, 16384, 32768):
    cnt = 0; tot = 0
    for i in range(0, min(N - L, 65536)):
        if FW[i] == FW[i + L]: cnt += 1
        tot += 1
    r = cnt / tot
    z = (r - 1/256) / math.sqrt((1/256)*(255/256)/tot)
    print(f"    L={L:>6d}  匹配率={r:.5f}  随机期望=0.00391  z={z:8.2f}"
          + ("   <<< 显著!" if z > 8 else ""))

print("\n" + "=" * 92)
print("C01-d. ★ 只在 1 KiB 网格上测 (原分析者的判据): 相邻 1KiB 块相异率")
print("=" * 92)
for base in (0x1200, 0x2000, 0x4000, 0x8000):
    eq = 0; tot = 0
    for i in range(base, min(base + 0x4000, N - 0x1000)):
        if FW[i] == FW[i + 0x1000]: eq += 1
        tot += 1
    print(f"    起点 0x{base:05X}: FW[i]==FW[i+0x1000] 占比 = {eq}/{tot} = {eq/tot:.5f}")

print("\n" + "=" * 92)
print("C01-e. 那 4 份零差异 1024B 表在哪 + 是否真的零差异")
print("=" * 92)
t0 = FW[0x8800:0x8800 + 1024]
print(f"  表定义: FW[0x08800 : 0x08800+1024]")
offs = []
for o in range(0, N - 1024 + 1):
    if FW[o:o+1024] == t0:
        offs.append(o)
print(f"  全文件零差异出现位置 (任意对齐) = {[hex(o) for o in offs]}")
print(f"  出现次数 = {len(offs)}")
print(f"  位置差 = {[offs[i+1]-offs[i] for i in range(len(offs)-1)]}")
print(f"  表内容前 48 B: {' '.join(f'{b:02x}' for b in t0[:48])}")
# 分布
from collections import Counter
c = Counter(t0)
print(f"  唯一字节数={len(c)}/256  最常见={c.most_common(5)}")
print(f"  熵 = {entropy(t0):.4f} bits/byte")
