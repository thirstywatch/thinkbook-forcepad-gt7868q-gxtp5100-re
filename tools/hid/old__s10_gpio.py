"""步骤10：GPIO Set/Reset 帮助函数的调用点上下文（找 bit-bang 迹象：同函数内多引脚翻转）"""
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

def arg_const(k, reg, back=12):
    """在 rows[k] 之前找 reg 的常量"""
    for j in range(k - 1, max(-1, k - back), -1):
        a, mn, ops = rows[j]
        if mn == "movs" or mn == "mov":
            m = re.match(r"(%s),\s*#(0x[0-9a-fA-F]+)" % reg, ops)
            if m:
                return int(m.group(2), 16)
        if mn == "movw" and ops.startswith(reg + ","):
            m = re.match(r"%s,\s*#(0x[0-9a-fA-F]+)" % reg, ops)
            lo = int(m.group(1), 16)
            if j + 1 < len(rows) and rows[j + 1][1] == "movt" and rows[j + 1][2].startswith(reg + ","):
                m2 = re.match(r"%s,\s*#(0x[0-9a-fA-F]+)" % reg, rows[j + 1][2])
                return (int(m2.group(1), 16) << 16) | lo
            return lo
        if re.match(r"%s\s*," % reg, ops) and mn not in ("str", "strh", "strb", "ldr", "ldrh", "ldrb", "cmp", "tst", "push", "pop", "cbz", "cbnz", "it", "bl", "blx", "b", "b.w"):
            return None
    return None

# 每个调用点所在函数（往上找最近的 push {...,lr}，且该地址下面有 movs r0,r0 对齐填充或前一条是 pop/bx）
def func_start(k):
    for j in range(k - 1, -1, -1):
        a, mn, ops = rows[j]
        if mn == "push" and "lr" in ops:
            return a
        if mn in ("pop",) and "pc" in ops:
            return rows[j + 1][0] if j + 1 < len(rows) else a
    return rows[0][0]

for tgt in (0x800F7FC, 0x800F80C):
    print("=== 调用 0x%08X 的上下文 ===" % tgt)
    byfunc = collections.defaultdict(list)
    for k, (pc, mn, ops) in enumerate(rows):
        if mn in ("bl", "blx") and ops == "#0x%x" % tgt:
            b = arg_const(k, "r0")
            m = arg_const(k, "r1")
            f = func_start(k)
            byfunc[f].append((pc, b, m))
    for f, lst in sorted(byfunc.items()):
        print(" 函数 0x%08X: %d 次" % (f, len(lst)))
        for pc, b, m in lst:
            print("    0x%08X  base=0x%08X pins/mask=0x%X (%d)" % (pc, b or 0, m or 0, m or 0))
    print()
