"""步骤9：找出所有把外设基址常量放进寄存器的点，并打印其后的使用上下文。
重点：GPIOA/GPIOB（Q3 bit-bang）、DMA（Q5）、USART/SPI（Q4）。
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
IDX = {r[0]: k for k, r in enumerate(rows)}

NAME = {0x40000000: "TIM2", 0x40000400: "TIM3", 0x40000800: "TIM4", 0x40000C00: "TIM5",
        0x40001000: "TIM6", 0x40001400: "TIM7", 0x40001800: "TIM8?", 0x40001C00: "?1C",
        0x40002000: "?20", 0x40002800: "RTC", 0x40002C00: "WWDG", 0x40003000: "IWDG",
        0x40003800: "SPI2", 0x40003C00: "SPI3", 0x40004400: "USART2", 0x40004800: "USART3",
        0x40004C00: "UART4", 0x40005000: "UART5", 0x40005400: "I2C1", 0x40005800: "I2C2",
        0x40006400: "CAN1", 0x40006C00: "BKP", 0x40007000: "PWR", 0x40007400: "DAC",
        0x40010000: "AFIO", 0x40010400: "EXTI", 0x40010800: "GPIOA", 0x40010C00: "GPIOB",
        0x40011000: "GPIOC", 0x40011400: "GPIOD", 0x40011800: "GPIOE", 0x40012400: "ADC1",
        0x40012C00: "TIM1", 0x40013000: "SPI1", 0x40013400: "TIM8", 0x40013800: "USART1",
        0x40013C00: "ADC3", 0x40014C00: "?14C", 0x40015000: "?150", 0x40015400: "?154",
        0x40020000: "DMA1", 0x40020400: "DMA2", 0x40021000: "RCC", 0x40022000: "FLASH"}

WANT = sys.argv[1] if len(sys.argv) > 1 else "all"

sites = []
for k, (pc, mn, ops) in enumerate(rows):
    if mn != "movw":
        continue
    mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", ops)
    if not mt:
        continue
    reg, lo = mt.group(1), int(mt.group(2), 16)
    if k + 1 >= len(rows):
        continue
    nxt = rows[k + 1]
    if nxt[1] not in ("movt",) or not nxt[2].startswith(reg + ","):
        # movt 可能隔一两条
        got = None
        for j in (k + 1, k + 2, k + 3):
            if j < len(rows) and rows[j][1] == "movt" and rows[j][2].startswith(reg + ","):
                got = j
                break
        if got is None:
            continue
        k2 = got
    else:
        k2 = k + 1
    mh = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)", rows[k2][2])
    if not mh:
        continue
    hi = int(mh.group(1), 16)
    val = (hi << 16) | lo
    if 0x40000000 <= val < 0x60000000:
        sites.append((pc, val, k2))

print("外设基址常量点 %d 个" % len(sites))

for pc, val, k2 in sites:
    nm = NAME.get(val, "?")
    if WANT != "all" and WANT not in nm:
        continue
    print("\n### 0x%08X  0x%08X %s" % (pc, val, nm))
    for j in range(k2 - 1, min(len(rows), k2 + 10)):
        a, mn, ops = rows[j]
        print("    0x%08X  %-8s %s" % (a, mn, ops))
