"""步骤12：尾部区是否可能被执行/被引用
- 是否有来自区外的分支目标落入尾部区
- 尾部区内是否有指向区外的 bl/b 目标（真代码通常会调用已知函数）
- 是否有 ldr [pc,#imm] 指向尾部区（当作数据引用）
"""
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
LO, HI = 0x08011A86, SEG_HI
T = re.compile(r"#(0x[0-9a-fA-F]+)")

print("=== 区外 -> 区内的分支 ===")
n = 0
for pc, mn, ops in rows:
    if mn in ("b", "b.w", "bl", "blx") or mn.startswith("b"):
        m = T.match(ops)
        if m:
            t = int(m.group(1), 16)
            if LO <= t <= HI and pc < LO:
                print("  0x%08X %s -> 0x%08X" % (pc, mn, t)); n += 1
print("  合计 %d" % n)

print("\n=== 区内 -> 区外的分支目标（真代码应大量调用已知函数）===")
out = collections.Counter()
for pc, mn, ops in rows:
    if LO <= pc <= HI and (mn in ("b", "b.w", "bl", "blx") or mn.startswith("b")):
        m = T.match(ops)
        if m:
            t = int(m.group(1), 16)
            if t < LO or t > HI:
                out[t] += 1
print("  不同区外目标 %d 个，前 30：" % len(out))
for t, c in out.most_common(30):
    print("    0x%08X x%d" % (t, c))

print("\n=== 全镜像 pc 相对 ldr 指向尾部区（把尾部当数据）===")
m2 = md()
data = seg()
n = 0
for pc, mn, ops in rows:
    if mn in ("ldr", "ldr.w") and "[pc" in ops:
        mm = re.search(r"\[pc,\s*#(0x[0-9a-fA-F]+)\]", ops)
        if not mm:
            continue
        tgt = ((pc + 4) & ~3) + int(mm.group(1), 16)
        if LO <= tgt <= HI:
            print("  0x%08X %s -> 0x%08X" % (pc, ops, tgt)); n += 1
print("  合计 %d" % n)

print("\n=== 尾部区内 ASCII 字符串 ===")
b = data[LO - SEG_LO:HI - SEG_LO + 1]
cur = bytearray()
found = []
for i, c in enumerate(b):
    if 32 <= c < 127:
        cur.append(c)
    else:
        if len(cur) >= 6:
            found.append((LO + i - len(cur), bytes(cur).decode()))
        cur = bytearray()
for a, s in found[:40]:
    print("  0x%08X  %r" % (a, s))
print("  合计 %d" % len(found))
