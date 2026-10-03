"""PA3 会不会被清？——穷举所有对 0x0800F7FC(GPIO_ResetBits) 的调用，
回溯 r0(端口) 与 r1(位掩码)，看有没有 (GPIOA, bit3) 的组合。

另外列出所有对 0x0800F80C(GPIO_SetBits) 的调用及其参数（应为 GPIOA,8 = PA3 置高）。
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ASM = os.path.join(HERE, "touchpad_TF100A_thumb.asm.txt")

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

idx_of = {r[0]: i for i, r in enumerate(rows)}
GPIOA, GPIOB = 0x40010800, 0x40010C00

def num(s):
    s = s.strip()
    return int(s, 16) if s.lower().startswith("0x") else int(s, 10)

def backtrack(i, reg, maxback=120):
    """从 rows[i] 往前找 reg 的最近一次确定赋值，返回 (值, 描述)。"""
    for j in range(i - 1, max(0, i - maxback) - 1, -1):
        mn, ops = rows[j][1], rows[j][2]
        # 函数边界
        if mn == "push" and "lr" in ops:
            return None, "函数边界"
        if mn == "movw":
            m = re.match(r"(%s),\s*#(0x[0-9a-fA-F]+|\d+)" % reg, ops)
            if m:
                lo = num(m.group(2))
                # 看下一条是否是 movt
                if j + 1 < len(rows) and rows[j + 1][1] == "movt" and rows[j + 1][2].startswith(reg + ","):
                    m2 = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+|\d+)", rows[j + 1][2])
                    if m2:
                        return (num(m2.group(1)) << 16) | lo, "movw/movt@%08X" % rows[j][0]
                return lo, "movw@%08X" % rows[j][0]
        if mn in ("movs", "mov", "mov.w"):
            m = re.match(r"(%s),\s*#(0x[0-9a-fA-F]+|\d+)\s*$" % reg, ops)
            if m:
                return num(m.group(2)), "%s@%08X" % (mn, rows[j][0])
            m = re.match(r"(%s),\s*(r\d+)\s*$" % reg, ops)
            if m:
                val, d = backtrack(j, m.group(2), 40)
                if val is not None:
                    return val, "mov<-%s(%s)" % (m.group(2), d)
                return None, "mov<-%s" % m.group(2)
        if mn in ("bl", "blx", "b.w"):
            return None, "调用边界@%08X" % rows[j][0]
        # 其它指令写了 reg 就停
        if re.match(r"(%s)(,|$)" % reg, ops) and not mn.startswith("cmp") and not mn.startswith("tst"):
            if mn.startswith("ldr") or mn.startswith("add") or mn.startswith("sub") or mn.startswith("orr") or mn.startswith("and") or mn.startswith("bic"):
                return None, "被 %s 覆盖@%08X" % (mn, rows[j][0])
    return None, "未找到"

for target, name in ((0x0800F7FC, "GPIO_ResetBits(BRR)"), (0x0800F80C, "GPIO_SetBits(BSRR)")):
    print("=" * 78)
    print("调用", name, "0x%08X 的站点：" % target)
    for i, (pc, mn, ops) in enumerate(rows):
        if mn in ("bl", "blx", "b.w") and ("#0x%x" % target) in ops.lower():
            r0, d0 = backtrack(i, "r0")
            r1, d1 = backtrack(i, "r1")
            port = {GPIOA: "GPIOA", GPIOB: "GPIOB"}.get(r0, hex(r0) if r0 is not None else "?")
            pin = ""
            if isinstance(r1, int):
                bits = [b for b in range(16) if r1 & (1 << b)]
                pin = "pin" + ",".join(str(b) for b in bits) if bits else "0"
            print("  %08X  %-5s %-12s  %s | r1=%s (%s)" % (pc, "", name.split("(")[0], port, hex(r1) if isinstance(r1, int) else r1, pin))
