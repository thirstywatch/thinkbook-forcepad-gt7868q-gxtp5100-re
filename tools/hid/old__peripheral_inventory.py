"""完整外设清单：扫出镜像里所有 (movw,movt) 拼出的 32 位常量，
筛出落在外设总线区间 (0x40000000-0x5FFFFFFF) 的基址并统计。

用途：证明 TF100A 除了 I2C1/USART1/TIM/GPIO/ADC 之外没有别的对外总线。
"""
import os, re, collections
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

# 名称表（STM32F1）
NAME = {
    0x40000000: "TIM2", 0x40000400: "TIM3", 0x40000800: "TIM4", 0x40000C00: "TIM5",
    0x40001000: "TIM6", 0x40001400: "TIM7", 0x40002800: "RTC", 0x40002C00: "WWDG",
    0x40003000: "IWDG", 0x40003800: "SPI2", 0x40003C00: "SPI3", 0x40004400: "USART2",
    0x40004800: "USART3", 0x40004C00: "UART4", 0x40005000: "UART5", 0x40005400: "I2C1",
    0x40005800: "I2C2", 0x40005C00: "USB", 0x40006400: "CAN1", 0x40006C00: "BKP",
    0x40007000: "PWR", 0x40007400: "DAC", 0x40007800: "CEC",
    0x40010000: "AFIO", 0x40010400: "EXTI", 0x40010800: "GPIOA", 0x40010C00: "GPIOB",
    0x40011000: "GPIOC", 0x40011400: "GPIOD", 0x40011800: "GPIOE",
    0x40012400: "ADC1", 0x40012800: "ADC2", 0x40012C00: "TIM1", 0x40013000: "SPI1",
    0x40013400: "TIM8", 0x40013800: "USART1", 0x40013C00: "ADC3",
    0x40020000: "DMA1", 0x40020400: "DMA2", 0x40021000: "RCC", 0x40022000: "FLASH",
    0xE000E000: "SCB/NVIC/SysTick", 0xE000ED00: "SCB", 0xE0042000: "DBGMCU",
}

found = collections.Counter()
detail = collections.defaultdict(list)
for i, (pc, mn, ops) in enumerate(rows):
    if mn != "movw":
        continue
    m = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", ops)
    if not m:
        continue
    reg, lo = m.group(1), int(m.group(2), 16)
    if i + 1 >= len(rows):
        continue
    nxt = rows[i + 1]
    if nxt[1] != "movt" or not nxt[2].startswith(reg + ","):
        continue
    m2 = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)", nxt[2])
    if not m2:
        continue
    val = (int(m2.group(1), 16) << 16) | lo
    if 0x40000000 <= val < 0x60000000 or 0xE0000000 <= val < 0xE0100000:
        found[val] += 1
        detail[val].append(pc)

print("=== 镜像里出现的外设基址（movw/movt 拼装）===")
for base, n in sorted(found.items()):
    nm = NAME.get(base, "?")
    print("  0x%08X  %-18s x%-3d  首见 %08X" % (base, nm, n, detail[base][0]))

print("\n=== 是否出现其它 I2C / SPI 基址 ===")
for base in (0x40005800, 0x40005C00, 0x40013000, 0x40003800, 0x40003C00):
    print("  0x%08X %-8s : %s" % (base, NAME.get(base, "?"), "出现" if base in found else "★ 未出现"))
