"""步骤7：把镜像里所有"代码指针"（4 字节对齐、带 Thumb 位、落在代码区）当作入口，
再做一轮递归下降，尽量覆盖"只被间接调用（函数指针表/回调）"的代码，
然后统计仍然未覆盖的区域 —— 用于回答"是否存在从未被调用的主机代码"。
"""
import sys, os, re, collections, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
m = md()

ptr_targets = set()
for o in range(0, len(data) - 3, 4):
    w = int.from_bytes(data[o:o + 4], "little")
    if 0x08005000 <= w <= SEG_HI and (w & 1):
        ptr_targets.add(w & ~1)
print("4 字节对齐的代码指针候选 %d 个" % len(ptr_targets))

entries = set(vec_entries(data)) | ptr_targets
code = recursive_descent(data, sorted(entries), m)
print("递归下降（含指针入口）指令数 = %d  覆盖 0x%08X-0x%08X" % (len(code), min(code), max(code)))

covered = bytearray(len(data))
for pc, i in code.items():
    o = pc - SEG_LO
    for k in range(i.size):
        if o + k < len(covered):
            covered[o + k] = 1
gaps = []
run = None
for o in range(len(covered)):
    if not covered[o]:
        if run is None:
            run = o
    else:
        if run is not None:
            gaps.append((run, o - run)); run = None
if run is not None:
    gaps.append((run, len(covered) - run))
print("\n未覆盖区段 %d 个，>16 字节的：" % len(gaps))
for o, n in sorted(gaps, key=lambda x: -x[1]):
    if n >= 16:
        print("  0x%08X..0x%08X  %d 字节" % (SEG_LO + o, SEG_LO + o + n - 1, n))

# 对每个未覆盖区段，尝试定点解码，看看"能不能"解出合理指令（判断是数据还是代码）
print("\n=== 未覆盖区段前 24 字节的解码尝试（判断数据/代码）===")
for o, n in sorted(gaps, key=lambda x: -x[1]):
    if n < 16:
        continue
    a = SEG_LO + o
    out = []
    for k in range(0, min(n, 24), 2):
        i = insn_at(m, data, a + k)
        out.append("%s" % (i.mnemonic if i else "??"))
    raw = data[o:o + 16].hex()
    print("  0x%08X len=%-5d %s | %s" % (a, n, raw, " ".join(out)))

# 有没有 "看起来像函数序言(push {...,lr})" 的地址落在未覆盖区
print("\n=== 未覆盖区里以 push{lR} 开头的可能函数 ===")
for o, n in sorted(gaps, key=lambda x: -x[1]):
    if n < 16:
        continue
    a = SEG_LO + o
    for k in range(0, n - 3, 2):
        i = insn_at(m, data, a + k)
        if i and i.mnemonic == "push" and "lr" in i.op_str:
            print("  0x%08X  %s %s   (区段起点 0x%08X, +0x%X)" % (a + k, i.mnemonic, i.op_str, a, k))
