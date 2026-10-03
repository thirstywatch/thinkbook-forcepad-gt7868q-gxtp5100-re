"""步骤4：调用点索引 —— 找出所有调用 I2C helper 的地址，并打印调用前 14 条指令上下文。
用法: s4_callers.py 0x800f9cc 0x800fa20 ...
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
m = md()
dec = {}
for o in range(0, len(data) - 1, 2):
    a = SEG_LO + o
    i = insn_at(m, data, a)
    if i is not None:
        dec[a] = i
ADDRS = sorted(dec.keys())
IDX = {a: k for k, a in enumerate(ADDRS)}

CALLS = collections.defaultdict(list)
for a in ADDRS:
    i = dec[a]
    if i.mnemonic in ("bl", "blx", "b.w", "b") and i.operands and i.operands[0].type == 2:
        CALLS[i.operands[0].imm].append((a, i.mnemonic))

def ctx(addr, n=14):
    k = IDX.get(addr)
    if k is None:
        return []
    out = []
    for j in range(max(0, k - n), k + 1):
        b = ADDRS[j]
        ii = dec[b]
        mark = "  <<<" if b == addr else ""
        out.append("    0x%08X  %-8s %s%s" % (b, ii.mnemonic, ii.op_str, mark))
    return out

if __name__ == "__main__":
    for t in sys.argv[1:]:
        t = int(t, 16)
        cs = CALLS.get(t, [])
        print("=== 0x%08X 被调用 %d 次 ===" % (t, len(cs)))
        for a, mn in cs:
            print("  -- 调用点 0x%08X (%s)" % (a, mn))
            for l in ctx(a):
                print(l)
        print()
