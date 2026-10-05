# -*- coding: utf-8 -*-
"""R5-1: 从 TF100A(载荷B) 反汇编里提取全部 32 位外设常量 + 判定 I2C 主/从 + AW86927 线索"""
import re, collections

ASM = r"<LAB>\touchpad-lab\bios-re\TF100A_thumb.asm.txt"
lines = open(ASM, encoding="utf-8", errors="replace").read().splitlines()
print(f"行数 {len(lines)}")

pat = re.compile(r"^([0-9A-Fa-f]{8})\s+(\S+)\s+(.*)$")
recs = []
for L in lines:
    m = pat.match(L.strip())
    if m:
        recs.append((int(m.group(1), 16), m.group(2), m.group(3)))

# ---- movw/movt 配对 ----
print("\n" + "=" * 90)
print("### 1 ★ TF100A 固件里的 32 位常量（movw+movt 配对）")
print("=" * 90)
pending = {}
consts = collections.Counter()
where = collections.defaultdict(list)
for i, (addr, mn, ops) in enumerate(recs):
    mm = re.match(r"#0x([0-9A-Fa-f]+)$", ops.strip())
    if not mm: continue
    val = int(mm.group(1), 16)
    mr = re.match(r"(\w+)", mn)
    # 目标寄存器：movw rN, #imm
    rm = re.match(r"^(r\d+|r1[0-2])$", ops.split(",")[0].strip())
    if mn in ("movw", "movt"):
        parts = ops.split(",")
        if len(parts) == 2 and re.match(r"^\s*(r\d+|r1[0-2])\s*$", parts[0]):
            reg = parts[0].strip()
            if mn == "movw":
                pending[reg] = (val, addr)
            elif reg in pending:
                lo, a0 = pending.pop(reg)
                full = (val << 16) | lo
                consts[full] += 1
                where[full].append((a0, addr))

PERIPH = {
    0x40005400: "I2C1", 0x40005800: "I2C2", 0x40013800: "USART1", 0x40004400: "USART2",
    0x40004800: "USART3", 0x40010800: "GPIOA", 0x40010C00: "GPIOB", 0x40011000: "GPIOC",
    0x40011400: "GPIOD", 0x40012400: "ADC1", 0x40013000: "SPI1", 0x40003800: "SPI2",
    0x40000000: "TIM2", 0x40000400: "TIM3", 0x40000800: "TIM4", 0x40002000: "TIM1",
    0x40007C00: "CAN", 0x40020000: "EXTI?", 0xE000E000: "SCB/SysTick",
    0x08000000: "FLASH_BASE", 0x20000000: "SRAM_BASE",
}
seen = set()
for v, n in consts.most_common():
    tag = ""
    base = v & 0xFFFFF000
    if v in PERIPH: tag = "  ★ " + PERIPH[v]
    elif base in PERIPH and base >= 0x40000000: tag = f"  ★ {PERIPH[base]} + 0x{v & 0xFFF:#x}"
    elif 0x08000000 <= v < 0x08020000: tag = "  (flash 内地址)"
    elif 0x20000000 <= v < 0x20020000: tag = "  (SRAM 内地址)"
    if n >= 1:
        print(f"  {v:#010x} ×{n:<3} 首现 @{where[v][0][0]:#010x}{tag}")

print("\n" + "=" * 90)
print("### 2 ★ I2C1 (0x40005400) 访问点：偏移 → 判定主/从")
print("=" * 90)
REGOFF = {0x00: "CR1", 0x04: "CR2", 0x08: "OAR1(自身地址)", 0x0C: "OAR2",
          0x10: "DR(数据)", 0x14: "SR1", 0x18: "SR2", 0x1C: "CCR", 0x20: "TRISE"}
i = 0
hits = 0
while i < len(recs) - 6:
    a, mn, ops = recs[i]
    if mn == "movw" and "#0x5400" in ops:
        reg = ops.split(",")[0].strip()
        # 往后找 movt rX, #0x4000 以及 ldr/str [rX, #imm]
        win = recs[i:i+24]
        base_ok = any(w[1] == "movt" and w[2].split(",")[0].strip() == reg and "#0x4000" in w[2] for w in win)
        if base_ok:
            for w in win:
                mo = re.search(r"\[%s,\s*#0x([0-9A-Fa-f]+)\]" % reg, w[2])
                if mo:
                    off = int(mo.group(1), 16)
                    print(f"    @{a:#010x} I2C1 访问 {REGOFF.get(off,'+0x%x'%off):<16} "
                          f"（{w[1]} {w[2]}）")
                    hits += 1
    i += 1
print(f"  共 {hits} 处")

print("\n" + "=" * 90)
print("### 3 ★ AW86927 线索：0x5A / 0xB4 的上下文")
print("=" * 90)
for i, (a, mn, ops) in enumerate(recs):
    if mn in ("movs",) and (", #0x5a" in ops or ", #0xb4" in ops):
        ctx = " | ".join(f"{recs[j][1]} {recs[j][2]}" for j in range(max(0, i-4), min(len(recs), i+5)))
        print(f"  @{a:#010x}  {mn} {ops}")
        print(f"      上下文: {ctx}")
