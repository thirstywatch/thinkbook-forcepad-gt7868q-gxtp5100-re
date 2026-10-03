# -*- coding: utf-8 -*-
"""B09. ★★★ 关键: 0x19850 附近是否为"半字字节序错"区域?
上面 capstone 只解出 74 条就停了 (遇到非法指令)。
逐条打印到停点, 定位停点; 并检验停点前后是否发生"字节序翻转"。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
FW = load()

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
print("=" * 100)
print("B09-a. 0x19850 顺序解码, 找在哪一条停止")
print("=" * 100)
last = None
cnt = 0
for ins in md.disasm(FW[0x19850:0x1A000], 0x19850):
    last = ins; cnt += 1
print(f"  解出 {cnt} 条, 最后一条 @0x{last.address:05X}: {last.mnemonic} {last.op_str}")
stop = last.address + last.size
print(f"  停止位置 (下一条尝试) = 0x{stop:05X}")
print(f"  停止处字节: {' '.join(f'{b:02x}' for b in FW[stop:stop+16])}")

# 用滑动扫描找所有非法点
print("\n" + "=" * 100)
print("B09-b. 滑动扫描: 0x19850-0x1A000 中所有非法指令落点")
print("=" * 100)
i = 0x19850
bads = []
while i < 0x1A000:
    g = None
    for ins in md.disasm(FW[i:i+16], i):
        g = ins; break
    if g is None:
        bads.append(i); i += 2; continue
    i += g.size
print(f"  非法落点数 = {len(bads)}")
for b in bads:
    print(f"    0x{b:05X}: {' '.join(f'{x:02x}' for x in FW[b:b+8])}")
print("\n  相邻非法点间隔:", [bads[k+1]-bads[k] for k in range(len(bads)-1)][:40])
print("  (若间隔恒为 4 或 8, 说明是穿插的特定模式)")

print("\n" + "=" * 100)
print("B09-c. 决定性: 检查真起点是 0x19848..0x19858 中哪一个 (连续解出条数最多)")
print("=" * 100)
for st in range(0x19848, 0x19858):
    n = 0
    for ins in md.disasm(FW[st:st+256], st):
        n += 1
    print(f"  起点 0x{st:05X}: 连续解出 {n} 条")
