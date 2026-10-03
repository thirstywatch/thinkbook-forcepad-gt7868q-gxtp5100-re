"""定位 TF100A 中指定外设的使用点，打印上下文（含所在函数入口推测）。"""
import re, sys, collections

ASM = sys.argv[1] if len(sys.argv) > 1 else "touchpad_TF100A_thumb.asm.txt"
L = [l for l in open(ASM, encoding="utf-8").read().splitlines() if l.strip()]

def imm(s):
    s = s.strip().lstrip("#")
    try: return int(s, 16)
    except ValueError: return None

regs = {}
events = []          # (行号, pc, 寄存器, 常量值)
for idx, l in enumerate(L):
    p = l.split(None, 2)
    if len(p) < 3: continue
    pc, mn, ops = p
    tgt = ops.split(",")[0].strip()
    if mn == "movw":
        v = imm(ops.split(",", 1)[1]); regs[tgt] = v if v is not None else 0
    elif mn == "movt":
        v = imm(ops.split(",", 1)[1])
        if v is not None:
            regs[tgt] = (regs.get(tgt, 0) & 0xFFFF) | (v << 16)
            events.append((idx, pc, tgt, regs[tgt]))
    elif mn not in ("cmp", "tst", "cmn"):
        regs.pop(tgt, None)

# 找到含该外设基址的"函数范围"：用 push{...,lr} 起点
def func_start(i):
    for j in range(i, max(-1, i - 400), -1):
        q = L[j].split(None, 2)
        if len(q) >= 3 and q[1] in ("push", "push.w") and "lr" in q[2]:
            return j
    return max(0, i - 40)

WANT = {0x40005400: "I2C1", 0x40012C00: "TIM1", 0x40013400: "TIM8",
        0x40000000: "TIM2", 0x40000400: "TIM3", 0x40010800: "GPIOA"}
I2C_OFF = {0x00: "CR1", 0x04: "CR2", 0x08: "OAR1", 0x0C: "OAR2", 0x10: "DR",
           0x14: "SR1", 0x18: "SR2", 0x1C: "CCR", 0x20: "TRISE"}
TIM_OFF = {0x00: "CR1", 0x04: "CR2", 0x0C: "DIER", 0x10: "SR", 0x14: "EGR", 0x18: "CCMR1",
           0x1C: "CCMR2", 0x20: "CCER", 0x24: "CNT", 0x28: "PSC", 0x2C: "ARR",
           0x2A: "RCR", 0x30: "RCR", 0x34: "CCR1", 0x38: "CCR2", 0x3C: "CCR3", 0x40: "CCR4", 0x44: "BDTR"}
GPIO_OFF = {0x00: "CRL", 0x04: "CRH", 0x08: "IDR", 0x0C: "ODR", 0x10: "BSRR", 0x14: "BRR"}

target = sys.argv[2] if len(sys.argv) > 2 else "0x40005400"
tval = int(target, 16)
name = WANT.get(tval, hex(tval))
print("=== %s (0x%X) 的使用点 ===" % (name, tval))
sites = []
for idx, pc, reg, val in events:
    if val != tval: continue
    for j in range(idx, min(idx + 20, len(L))):
        q = L[j].split(None, 2)
        if len(q) < 3: continue
        mn2, ops2 = q[1], q[2]
        if mn2 in ("ldr", "str", "ldrh", "strh", "ldrb", "strb", "ldrsb", "ldrsh"):
            m = re.search(r"\[%s(\s*,\s*#0x([0-9a-f]+))?\s*\]" % re.escape(reg), ops2)
            off = int(m.group(2), 16) if (m and m.group(2)) else 0
            offmap = I2C_OFF if tval == 0x40005400 else (TIM_OFF if tval in (0x40000000,0x40000400,0x40012C00,0x40013400) else GPIO_OFF)
            sites.append((j, pc, reg, off, offmap.get(off, "?"), mn2, ops2))
            break

print("访问点 %d 处" % len(sites))
# 按函数分组
groups = collections.OrderedDict()
for j, pc, reg, off, offn, mn2, ops2 in sites:
    fs = func_start(j)
    groups.setdefault(fs, []).append((j, pc, reg, off, offn, mn2, ops2))
print("分布在 %d 个函数里\n" % len(groups))
for k, (fs, items) in enumerate(groups.items()):
    print("=" * 72)
    print("### 函数 %d：入口推测 0x%s  —— 命中 %d 处：%s" % (
        k + 1, L[fs].split()[0], len(items),
        ", ".join("%s+0x%02X(%s)" % (it[2], it[3], it[4]) for it in items[:12])))
    lo = max(0, fs - 2); hi = min(len(L), items[-1][0] + 8)
    if hi - lo > 90: hi = lo + 90
    for m in range(lo, hi):
        mark = "   " if m != fs else ">> "
        print(mark + L[m])
