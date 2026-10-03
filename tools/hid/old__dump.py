"""按地址范围从线性反汇编文本里 dump 指令。用法: dump.py 0x8008A70 0x8008B70"""
import sys

ASM = "touchpad_TF100A_thumb.asm.txt"
L = [l for l in open(ASM, encoding="utf-8").read().splitlines() if l.strip()]

def parse(l):
    p = l.split(None, 2)
    return (int(p[0], 16), p[1], p[2] if len(p) > 2 else "") if len(p) >= 2 else None

rows = [parse(l) for l in L]
rows = [r for r in rows if r]

lo, hi = int(sys.argv[1], 16), int(sys.argv[2], 16)
for pc, mn, ops in rows:
    if lo <= pc <= hi:
        mark = ">>" if pc == lo else "  "
        print("%s %08X  %-9s %s" % (mark, pc, mn, ops))

# 顺带列出这段里出现的 bl 目标，方便追函数名
tg = sorted({ops.split("#")[-1] for pc, mn, ops in rows if lo <= pc <= hi and mn in ("bl", "b.w", "blx") and "#" in ops})
print("\n[本段 bl/b 目标] " + ", ".join(tg))
