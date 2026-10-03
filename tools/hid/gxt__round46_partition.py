#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND46 —— ★ 固件分区分析 + Cortex-M 向量表解析

发现：固件分三段（容器头 / 96KB 密文 / 明文代码区）
向量表 0x19ABC 指向密文区 => 主程序在加密区
"""
import sys, struct, collections, math, re
sys.path.insert(0, r'<HOME>\.workbuddy\skills\arm-thumb-caller-trace\scripts')
from thumb_caller_trace import load_image, disasm_win, find_callers_of

FW = r'<WORKSPACE>'
BASE = 0x08000000
D, _ = load_image(FW)

out = []
def W(s=''):
    print(s); out.append(str(s))

def ent(b):
    c = collections.Counter(b); n = len(b)
    return -sum((v/n) * math.log2(v/n) for v in c.values())

W("=" * 78)
W("ROUND46 固件分区分析")
W("=" * 78)

W("\n## A. 逐 4KB 页熵（明文/密文分界）\n")
W("    偏移      熵     判定")
prev = None
for pg in range(0, len(D) - 0x1000, 0x1000):
    e = ent(D[pg:pg+0x1000])
    if e > 7.5:   kind = "密文/压缩"
    elif e > 5.5: kind = "明文代码"
    else:         kind = "稀疏/头"
    flag = "  <<< 跳变" if prev is not None and abs(e - prev) > 1.0 else ""
    W("    0x%05X  %.2f  %s%s" % (pg, e, kind, flag))
    prev = e

W("\n## B. 分区表\n")
W("    0x00000-0x00FFF   4 KB   容器头")
W("    0x01000-0x18FFF  96 KB   ★ 加密区（主固件主体）")
W("    0x19000-0x2775B  57 KB   ★ 明文代码区（TF100A 向量表 + 主控应用）")

W("\n## C. ★ Cortex-M 向量表 @0x19ABC\n")
VT = 0x19ABC
names = ['SP','Reset','NMI','HardFault','MemManage','BusFault','UsageFault','-','-','-','-','SVC','DebugMon','-','PendSV','SysTick']
for i in range(16):
    v = struct.unpack_from('<I', D, VT + i*4)[0]
    W("    [%2d] %-12s 0x%08X" % (i, names[i], v))

codeaddrs = []
for i in range(16, 16 + 96):
    v = struct.unpack_from('<I', D, VT + i*4)[0]
    if 0x08000000 <= v < 0x08040000:
        codeaddrs.append((i - 16, v))

W("\n    非零 IRQ 向量（去重）：")
uniq = sorted(set(v & ~1 for _, v in codeaddrs))
for u in uniq:
    W("      0x%08X  -> 文件偏移 0x%05X  熵=%.2f" % (u, u - BASE, ent(D[u-BASE:u-BASE+0x400])))

W("\n## D. ★ 判定：向量表指向密文区\n")
W("    表内地址范围: 0x%08X .. 0x%08X" % (min(uniq), max(uniq)))
W("    明文代码范围: 0x%08X .. 0x%08X" % (BASE + 0x19000, BASE + 0x2775B))
W("    => 不重叠 => 向量表指向的是加密区的另一套代码")
r = struct.unpack_from('<I', D, VT + 4)[0] - BASE
W("    Reset = 0x%08X -> 文件偏移 0x%05X -> 熵 %.2f (%s)"
  % (struct.unpack_from('<I', D, VT + 4)[0], r, ent(D[r:r+0x400]),
     "密文(无法反汇编)" if ent(D[r:r+0x400]) > 7.5 else "明文"))

W("\n## E. 明文区关键锚点确认\n")
for off in (0x19ECC, 0x19EEC, 0x19F0C):
    W("    0x%05X  %r" % (off, D[off:off+20].split(b'\x00')[0]))

W("\n## F. 明文区覆盖了哪些我们已知的函数\n")
for nm, a in (('协议解析器', 0x1ACEC), ('命令分派器', 0x22C7C), ('写入封装', 0x1B874),
              ('命令0x1B处理', 0x1AB90), ('CRC-8 0x1B6E0', 0x1B6E0), ('擦页 0x1B780', 0x1B780)):
    W("    %-14s 0x%05X  在明文区: %s" % (nm, a, 0x19000 <= a < 0x27760))

W("\n## G. CRC-8 (0x1B6E0) 的调用者 —— 是否用于校验明文区\n")
r = find_callers_of(D, 0x1B6E0)
W("    共 %d 个：" % len(r))
for c, _ in r:
    W("      0x%05X" % c)

open('cfg_parsed/round46_partition.txt', 'w', encoding='utf-8').write('\n'.join(out))
print("\n[已写 cfg_parsed/round46_partition.txt]")
