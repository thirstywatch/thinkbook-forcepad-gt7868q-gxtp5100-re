"""步骤6：基于已有 asm 线性清单（20314 条真实指令地址）建立调用图，
列出指定函数的全部调用点及上下文（避免 superset 解码的错位噪声）。
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ASM

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
ADDR = [r[0] for r in rows]
IDX = {a: k for k, a in enumerate(ADDR)}
INS = {r[0]: (r[1], r[2]) for r in rows}

CALLS = collections.defaultdict(list)
for pc, mn, ops in rows:
    if mn in ("bl", "blx", "b.w", "b") and ops.startswith("#"):
        CALLS[int(ops[1:], 16)].append((pc, mn))

def show(addr, n=16):
    k = IDX.get(addr)
    if k is None:
        print("    (地址不在线性清单内)")
        return
    for j in range(max(0, k - n), k + 1):
        b = ADDR[j]
        mn, ops = INS[b]
        print("      0x%08X  %-8s %s%s" % (b, mn, ops, "   <<<" if b == addr else ""))

if __name__ == "__main__":
    for t in sys.argv[1:]:
        t = int(t, 16)
        cs = CALLS.get(t, [])
        print("=== 0x%08X (%s) 调用点 %d 个 ===" % (t, INS.get(t, ("?",))[0], len(cs)))
        for a, mn in cs:
            print("   -- 0x%08X (%s)" % (a, mn))
            show(a)
        print()
