"""§五 判据 · 第三步（修正版）：穷举对 I2C1 (0x40005400) 寄存器块的访问。

修正点（v1 的 bug）：
  · 函数边界 `push {...,lr}` 处必须清空所有寄存器常量（v1 未清，导致 r0 的
    I2C1 基址跨越函数边界泄漏到下一个函数，把 ctx 结构体访问 0x100+ 误判成寄存器访问）
  · `b.w`（尾调用）也要让 r0-r3 失效（v1 只处理 bl/blx）
  · I2C1 寄存器块只有 0x00-0x23，偏移 >= 0x24 一律标为"疑似假阳性"并单独列出

自校验：本脚本必须复现"movw #0x54NN + movt #0x4000"的全部 13 个真实站点。
"""
import os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ASM = os.path.join(HERE, "touchpad_TF100A_thumb.asm.txt")
I2C_BASE = 0x40005400
OFFNAME = {0x00: "CR1", 0x04: "CR2", 0x08: "OAR1", 0x0C: "OAR2", 0x10: "DR",
           0x14: "SR1", 0x18: "SR2", 0x1C: "CCR", 0x20: "TRISE"}

rows = []
for l in open(ASM, encoding="utf-8"):
    l = l.rstrip()
    if not l.strip():
        continue
    p = l.split(None, 2)
    if len(p) < 2:
        continue
    try:
        pc = int(p[0], 16)
    except ValueError:
        continue
    rows.append((pc, p[1], p[2] if len(p) > 2 else ""))

KNOWN = {}
pending_movw = {}
hits = []
func_entry = None
WRITE_MN = ("str", "strb", "strh", "str.w", "strb.w", "strh.w", "stm", "stmia")


def invalidate(r):
    KNOWN.pop(r, None)


for pc, mn, ops in rows:
    # ---------- 函数边界：清空所有常量 ----------
    if mn == "push" and "lr" in ops:
        KNOWN.clear()
        pending_movw.clear()
        func_entry = pc
    # 函数出口：叶函数（无 push）只能靠 bx lr / pop {..,pc} 识别，必须清空
    if (mn == "bx" and "lr" in ops) or (mn.startswith("pop") and "pc" in ops):
        KNOWN.clear()
        pending_movw.clear()

    # ---------- 记录对已知基址的访存 ----------
    for mm in re.finditer(r"\[(r\d+)(?:,\s*#(0x[0-9a-fA-F]+))?\]", ops):
        reg = mm.group(1)
        off = int(mm.group(2), 16) if mm.group(2) else 0
        if KNOWN.get(reg) == I2C_BASE:
            kind = "READ" if mn.startswith("ldr") else ("WRITE" if mn.split(".")[0].startswith("str") else mn)
            hits.append((pc, func_entry, kind, reg, off, mn, ops))

    # ---------- 数据流更新 ----------
    if mn == "movw":
        mm = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", ops)
        if mm:
            pending_movw[mm.group(1)] = int(mm.group(2), 16)
            invalidate(mm.group(1))
        continue
    if mn == "movt":
        mm = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", ops)
        if mm and mm.group(1) in pending_movw:
            r = mm.group(1)
            KNOWN[r] = (int(mm.group(2), 16) << 16) | pending_movw.pop(r)
        continue

    if mn in ("bl", "blx", "b.w", "bl.w"):          # 调用 / 尾调用
        for r in ("r0", "r1", "r2", "r3"):
            invalidate(r)
        continue

    if mn == "mov" or mn == "mov.w":
        mm = re.match(r"(r\d+),\s*(r\d+)\s*$", ops)
        if mm:
            dst, src = mm.group(1), mm.group(2)
            if src in KNOWN:
                KNOWN[dst] = KNOWN[src]
            else:
                invalidate(dst)
        else:
            mm = re.match(r"(r\d+)", ops)
            if mm:
                invalidate(mm.group(1))
        continue

    # 其余指令：目的寄存器一律失效（保守）
    dst = ops.split(",")[0].strip()
    if re.fullmatch(r"r\d+", dst) or re.fullmatch(r"r\d+!", dst):
        invalidate(dst)
    else:
        mm = re.match(r"(r\d+)", ops)
        if mm:
            invalidate(mm.group(1))

# ---------------- 输出 ----------------
print("=== 对 I2C1 (0x40005400) 寄存器块的【全部】访问 ===")
print(f"{'PC':>8}  {'kind':<5} {'off':<6} {'reg':<6} {'所在函数':<10} 指令")
for pc, fe, kind, reg, off, mn, ops in hits:
    tag = OFFNAME.get(off, "!0x%02X 越界" % off)
    print(f"  {pc:08X}  {kind:<5} +0x{off:02X}  {reg:<4}  {fe:08X}  {mn:<9} {ops}")

real = [h for h in hits if h[4] < 0x24]
print(f"\n合计 {len(hits)} 处；其中偏移在 I2C1 寄存器范围内(<0x24)的 {len(real)} 处")
print("\n=== 偏移汇总（只统计 <0x24）===")
c = collections.Counter(h[4] for h in real)
for off, n in sorted(c.items()):
    print(f"  +0x{off:02X} {OFFNAME.get(off,'?'):<6} {n} 处")

print("\n=== ★ 写操作（<0x24）===")
for pc, fe, kind, reg, off, mn, ops in real:
    if kind == "WRITE":
        print(f"  {pc:08X}  +0x{off:02X} {OFFNAME.get(off,'?'):<6} {mn} {ops}")

print("\n=== 自校验：movw #0x54NN + movt #0x4000 的真实站点 ===")
n = 0
for i, (pc, mn, ops) in enumerate(rows):
    if mn == "movw" and re.search(r"#0x54[0-9a-fA-F]{2}", ops):
        for c2 in rows[i+1:i+3]:
            if c2[1] == "movt" and "#0x4000" in c2[2]:
                n += 1
                print(f"  {pc:08X}  {ops}")
                break
print(f"  共 {n} 个真实 I2C1 基址/偏移站点")
