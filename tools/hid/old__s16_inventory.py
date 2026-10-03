"""步骤16：修正版外设基址清单 —— 同时覆盖
(a) movw+movt 拼装
(b) movs rX,#0 + movt rX,#hi （低 16 位为 0 的基址，如 0x40010000/0x40020000）
(c) movs rX,#imm + movt
并统计每个基址的使用点。
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
m = md()
NAME = {0x40000000: "TIM2", 0x40000400: "TIM3", 0x40000800: "TIM4", 0x40000C00: "TIM5",
        0x40001000: "TIM6", 0x40001400: "TIM7", 0x40002800: "RTC", 0x40002C00: "WWDG",
        0x40003000: "IWDG", 0x40003800: "SPI2", 0x40003C00: "SPI3", 0x40004400: "USART2",
        0x40004800: "USART3", 0x40004C00: "UART4", 0x40005000: "UART5", 0x40005400: "I2C1",
        0x40005800: "I2C2", 0x40005C00: "USB", 0x40006400: "CAN1", 0x40006C00: "BKP",
        0x40007000: "PWR", 0x40010000: "AFIO", 0x40010400: "EXTI", 0x40010800: "GPIOA",
        0x40010C00: "GPIOB", 0x40011000: "GPIOC", 0x40011400: "GPIOD", 0x40011800: "GPIOE",
        0x40012400: "ADC1", 0x40012C00: "TIM1", 0x40013000: "SPI1", 0x40013400: "TIM8",
        0x40013800: "USART1", 0x40013C00: "ADC3", 0x40020000: "DMA1", 0x40020400: "DMA2",
        0x40021000: "RCC", 0x40022000: "FLASH", 0xE000E000: "SysTick/SCB", 0xE000ED00: "SCB",
        0xE0042000: "DBGMCU"}

found = collections.Counter()
det = collections.defaultdict(list)
for o in range(0, len(data) - 7, 2):
    a = SEG_LO + o
    i = insn_at(m, data, a)
    if i is None:
        continue
    # (a) movw+movt
    if i.mnemonic == "movw":
        mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+|[0-9]+)", i.op_str)
        if mt:
            reg, lo = mt.group(1), int(mt.group(2), 16)
            j = insn_at(m, data, a + 4)
            if j is not None and j.mnemonic == "movt" and j.op_str.startswith(reg + ","):
                m2 = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)", j.op_str)
                if m2:
                    v = (int(m2.group(1), 16) << 16) | lo
                    found[v] += 1; det[v].append(a)
    # (b)/(c) movs/mov + movt
    if i.mnemonic in ("movs", "mov"):
        mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+|[0-9]+)", i.op_str)
        if mt:
            reg, lo = mt.group(1), int(mt.group(2), 16)
            j = insn_at(m, data, a + 4)
            if j is not None and j.mnemonic == "movt" and j.op_str.startswith(reg + ","):
                m2 = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)", j.op_str)
                if m2 and lo < 0x10000:
                    v = (int(m2.group(1), 16) << 16) | lo
                    found[v] += 1; det[v].append(a)

print("=== 修正版外设/系统基址清单（movw+movt 或 movs+movt）===")
for v, c in sorted(found.items()):
    if (0x40000000 <= v < 0x60000000) or (0xE0000000 <= v < 0xE0100000):
        print("  0x%08X %-14s x%-3d 首见 0x%08X" % (v, NAME.get(v, "?"), c, sorted(det[v])[0]))

print("\n=== 关心项是否存在 ===")
for v in (0x40005400, 0x40005800, 0x40013000, 0x40003800, 0x40003C00, 0x40020000, 0x40020400, 0x40006400, 0x40005C00):
    print("  0x%08X %-8s : %s" % (v, NAME.get(v, "?"), "出现 %d 次: %s" % (found[v], ["0x%08X" % x for x in sorted(det[v])]) if v in found else "★ 未出现"))
