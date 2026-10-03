"""步骤1：验证映射、向量表、递归下降建立代码图；并与已有 asm 文本对拍。"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
print("段长 = 0x%X (%d 字节)" % (len(data), len(data)))

print("\n=== 向量表 0x08005000-0x0800517F ===")
for i in range(0, 0x180, 4):
    w = int.from_bytes(data[i:i + 4], "little")
    tag = ""
    if 0x08005000 <= w <= SEG_HI and (w & 1):
        tag = "  -> code 0x%08X" % (w & ~1)
    print("  0x%08X  [%02X] 0x%08X%s" % (VEC_LO + i, i, w, tag))

# 复位向量（第 1 项，偏移 4）
rv = int.from_bytes(data[4:8], "little")
print("\n复位向量(off 4) = 0x%08X   thumb=%s" % (rv, bool(rv & 1)))

# 对拍：asm 文本 vs 原始字节定点解码
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
asm = {pc: (mn, ops) for pc, mn, ops in rows}
print("asm 文本行数 = %d, 地址范围 0x%08X-0x%08X" % (len(rows), rows[0][0], rows[-1][0]))
uniq = len(set(pc for pc, _, _ in rows))
print("唯一地址数 = %d" % uniq)

m = md()
# 对拍：对每个 asm 行地址，用 capstone 定点解码，看助记符是否一致
bad = 0
checked = 0
for pc, mn, ops in rows:
    if pc < SEG_LO or pc > SEG_HI - 3:
        continue
    i = insn_at(m, data, pc)
    checked += 1
    if i is None:
        continue
    exp = mn
    got = i.mnemonic
    if exp != got and not (exp == "b.w" and got == "b") and not (exp.startswith("v") and got.startswith("v")):
        bad += 1
        if bad <= 15:
            print("  不一致 0x%08X: asm='%s %s'  capstone='%s %s'" % (pc, mn, ops, got, i.op_str))
print("对拍 checked=%d 不一致=%d" % (checked, bad))

# 递归下降
entries = vec_entries(data)
print("\n向量表代码入口 %d 个" % len(entries))
code = recursive_descent(data, entries, m)
print("递归下降得到指令 %d 条，覆盖 0x%08X-0x%08X" % (len(code), min(code), max(code)))

# bl 目标（递归下降已跟，这里统计函数入口）
tg = collections.Counter()
for pc, i in code.items():
    if i.mnemonic in ("bl", "blx") and i.operands and i.operands[0].type == 2:
        tg[i.operands[0].imm] += 1
print("bl/blx 目标 %d 个" % len(tg))

np = 0
for pc, i in code.items():
    if pc not in tg and i.mnemonic in ("push",) and "lr" in i.op_str:
        np += 1
funcs = sorted(set(list(tg.keys()) + [pc for pc, i in code.items() if i.mnemonic == "push" and "lr" in i.op_str]))
print("候选函数入口 %d 个" % len(funcs))

# 未覆盖字节（可能是数据/字面量池或漏掉的代码）
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
            gaps.append((run, o - run))
            run = None
if run is not None:
    gaps.append((run, len(covered) - run))
print("\n未覆盖区段 %d 段（含字面量池/数据），最大 8 段：" % len(gaps))
for o, n in sorted(gaps, key=lambda x: -x[1])[:8]:
    print("  0x%08X..0x%08X (%d 字节)" % (SEG_LO + o, SEG_LO + o + n - 1, n))

import json
json.dump({"code": sorted(code.keys())}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "codemap.json"), "w"))
print("\ncodemap.json 已写出")
