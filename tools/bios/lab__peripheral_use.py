"""TF100A 外设使用分析：折叠 movw/movt，定位 TIM1/TIM8/ADC1/I2C1/GPIOA 的寄存器访问。"""
import re, collections, sys

ASM = sys.argv[1] if len(sys.argv) > 1 else "touchpad_TF100A_thumb.asm.txt"
L = [l for l in open(ASM, encoding="utf-8").read().splitlines() if l.strip()]

def imm(s):
    s = s.strip().lstrip("#")
    try:
        return int(s, 16)
    except ValueError:
        return None

regs = {}
events = []
for idx, l in enumerate(L):
    p = l.split(None, 2)
    if len(p) < 3:
        continue
    pc, mn, ops = p
    tgt = ops.split(",")[0].strip()
    if mn == "movw":
        v = imm(ops.split(",", 1)[1])
        regs[tgt] = v if v is not None else 0
    elif mn == "movt":
        v = imm(ops.split(",", 1)[1])
        if v is not None:
            regs[tgt] = (regs.get(tgt, 0) & 0xFFFF) | (v << 16)
            events.append((idx, pc, tgt, regs[tgt]))
    elif mn not in ("cmp", "tst", "cmn"):
        regs.pop(tgt, None)

KEY = {0x40012C00: "TIM1", 0x40013400: "TIM8", 0x40000400: "TIM3",
       0x40012400: "ADC1", 0x40005400: "I2C1", 0x40010800: "GPIOA", 0x40010C00: "GPIOB"}
OFF = {0x00: "CR1", 0x04: "CR2", 0x08: "SMCR", 0x0C: "DIER", 0x10: "SR", 0x14: "EGR",
       0x18: "CCMR1", 0x1C: "CCMR2", 0x20: "CCER", 0x24: "CNT", 0x28: "PSC", 0x2C: "ARR",
       0x30: "RCR", 0x34: "CCR1", 0x38: "CCR2", 0x3C: "CCR3", 0x40: "CCR4",
       0x44: "BDTR<死区>", 0x48: "DCR", 0x4C: "DMAR",
       0x00: "CRL(GPIO)", 0x04: "CRH(GPIO)", 0x08: "IDR", 0x0C: "ODR", 0x10: "BSRR", 0x14: "BRR"}

hits = collections.Counter()
detail = []
for idx, pc, reg, val in events:
    if val not in KEY:
        continue
    for j in range(idx, min(idx + 16, len(L))):
        q = L[j].split(None, 2)
        if len(q) < 3:
            continue
        mn2, ops2 = q[1], q[2]
        if mn2 in ("ldr", "str", "ldrh", "strh", "ldrb", "strb"):
            m = re.search(r"\[%s[^\]]*#0x([0-9a-f]+)" % re.escape(reg), ops2)
            if m:
                off = int(m.group(1), 16)
                hits[(KEY[val], off)] += 1
                detail.append((pc, KEY[val], off, mn2, OFF.get(off, ""), ops2))

print("=== 寄存器访问统计（TIM1/TIM8/TIM3/ADC1/I2C1/GPIOA/B）===")
for (unit, off), n in sorted(hits.items(), key=lambda x: (-x[1], x[0])):
    print("   %-6s +0x%02X  %-12s ×%d" % (unit, off, OFF.get(off, ""), n))

print("\n=== ★ BDTR（高级定时器死区寄存器）使用点 ===")
bd = [d for d in detail if d[4].startswith("BDTR")]
if bd:
    for pc, unit, off, mn, nm, ops in bd:
        print("   ★ %s  %-5s +0x%02X (%s)  ->  %s" % (pc, unit, off, mn, ops))
else:
    print("   （未发现）")

print("\n=== ★ 互补输出相关（CCER / CR2 / CCMR1·2）使用点 ===")
for pc, unit, off, mn, nm, ops in detail:
    if unit in ("TIM1", "TIM8") and off in (0x00, 0x04, 0x18, 0x1C, 0x20, 0x28, 0x2C):
        print("   %s  %-5s +0x%02X %-8s %-10s %s" % (pc, unit, off, mn, nm, ops))

print("\n=== ★ GPIOA 使用点（前 30）===")
n = 0
for pc, unit, off, mn, nm, ops in detail:
    if unit == "GPIOA":
        print("   %s  GPIOA+0x%02X %-8s %-11s %s" % (pc, off, mn, nm, ops))
        n += 1
        if n >= 30:
            break
