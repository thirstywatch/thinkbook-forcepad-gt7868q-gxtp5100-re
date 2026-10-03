# -*- coding: utf-8 -*-
"""B04. 精确定位 Thumb 代码段边界 + 找向量表 + 定基址。
方法: 以 256 B 为窗口滑动，计算"非法指令率"，画曲线找跃变点。
判据已标定: 真代码<0.01, 随机~0.05, 全FF=1.0
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *

FW = load(); N = len(FW)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

def bad_rate(buf, base, steps=4000):
    i = 0; L = len(buf); ok = 0; bad = 0
    while i < L and (ok+bad) < steps:
        got = None
        for ins in md.disasm(buf[i:i+16], base+i):
            got = ins; break
        if got is None:
            bad += 1; i += 2; continue
        ok += 1; i += got.size
    return bad/(ok+bad) if (ok+bad) else -1

print("=" * 92)
print("B04-a. 非法指令率曲线 (256B 窗口 / 256B 步长), 全文件")
print("=" * 92)
W = 256
rows = []
for off in range(0, N - W, W):
    br = bad_rate(FW[off:off+W], 0x08000000+off)
    rows.append((off, br))
# 打印关键区间
print("  低区 0x00000-0x1A000 采样 + 全 0x18E00-0x19C00 细看 + 尾区")
for off, br in rows:
    flag = ""
    if 0x18800 <= off <= 0x19E00: flag = " <<<"
    if off < 0x3000 or (0x18000 <= off <= 0x1A000) or off >= 0x25000:
        print(f"    0x{off:05X} 非法率={br:.4f}{flag}")

print("\n" + "=" * 92)
print("B04-b. 逐 64B 精扫 0x18E00 - 0x19C00 (找精确边界)")
print("=" * 92)
for off in range(0x18C00, 0x19A00, 64):
    br = bad_rate(FW[off:off+64], 0x08000000+off, steps=64)
    bar = "#" * int(br*60)
    print(f"    0x{off:05X} bad={br:.4f} {bar}")

print("\n" + "=" * 92)
print("B04-c. 逐 64B 精扫 0x25000 - 0x26000 (看代码段是否延伸到文件尾)")
print("=" * 92)
for off in range(0x24800, 0x26000, 64):
    br = bad_rate(FW[off:off+64], 0x08000000+off, steps=64)
    bar = "#" * int(br*60)
    print(f"    0x{off:05X} bad={br:.4f} {bar}")

print("\n" + "=" * 92)
print("B04-d. ★ 向量表搜索: 找 [u32 SP][u32 Reset] 使 SP 落在 RAM 且 Reset 落在代码区")
print("=" * 92)
# Cortex-M: RAM 常见 0x20000000 或 0x10000000 / 0x1FFF0000。代码常见 0x08000000/0x00000000
RAM_CANDS = [(0x20000000, 0x20040000), (0x10000000, 0x10010000),
             (0x1FFF0000, 0x20000000), (0x00000000, 0x00010000)]
hits = []
for off in range(0, N - 64, 4):
    sp = le32(FW, off)
    rs = le32(FW, off + 4)
    sp_ok = any(lo < sp <= hi and sp % 4 == 0 for lo, hi in RAM_CANDS)
    rs_ok = rs % 2 == 1 and 0x100 <= rs < 0x1000000   # Thumb bit set + 合理
    if sp_ok and rs_ok:
        hits.append((off, sp, rs))
print(f"  命中数 = {len(hits)}")
for off, sp, rs in hits[:30]:
    print(f"    off=0x{off:05X}  SP=0x{sp:08X}  Reset=0x{rs:08X}")

print("\n  放宽: 只要求 SP 落在 0x20000000-0x20080000 且 reset 为奇数")
hits2 = []
for off in range(0, N - 64, 4):
    sp = le32(FW, off); rs = le32(FW, off+4)
    if 0x20000000 <= sp < 0x20080000 and (rs & 1) and 0x1000 <= rs < 0x400000:
        hits2.append((off, sp, rs))
print(f"  命中数 = {len(hits2)}")
for off, sp, rs in hits2[:30]:
    print(f"    off=0x{off:05X}  SP=0x{sp:08X}  Reset=0x{rs:08X}")
