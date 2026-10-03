# -*- coding: utf-8 -*-
"""round28_periph_sites.py —— 外设常量与其引用点全表（回答 0x40003000 是什么）"""
import os
D = open(r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN", "rb").read()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round28_periph_sites.txt")
occur = {}
n = len(D)
for o in range(0, n - 4, 2):
    hw1 = D[o] | (D[o+1] << 8)
    if (hw1 >> 11) != 0b11110:
        continue
    if (hw1 & 0x0FF0) != 0x240:
        continue
    hw2 = D[o+2] | (D[o+3] << 8)
    imm16 = ((hw1 & 0xF) << 12) | (((hw1 >> 10) & 1) << 11) | (((hw2 >> 12) & 7) << 8) | (hw2 & 0xFF)
    rd = (hw2 >> 8) & 0xF
    for o2 in range(o + 2, min(o + 16, n - 4)):
        g1 = D[o2] | (D[o2+1] << 8)
        if (g1 >> 11) != 0b11110:
            continue
        if (g1 & 0x0FF0) != 0x2C0:
            continue
        g2 = D[o2+2] | (D[o2+3] << 8)
        if ((g2 >> 8) & 0xF) != rd:
            continue
        hi16 = ((g1 & 0xF) << 12) | (((g1 >> 10) & 1) << 11) | (((g2 >> 12) & 7) << 8) | (g2 & 0xFF)
        v = (hi16 << 16) | imm16
        occur.setdefault(v, []).append(o)

lines = []
def w(s=""):
    lines.append(str(s)); print(s)

KNOWN = {
    0x40021000: "RCC base", 0x40021004: "RCC_CR? (0x04)", 0x40021008: "RCC_CFGR(0x08)",
    0x4002102C: "RCC_APB1ENR?(0x2C)",
    0x40022000: "FLASH base/ACR", 0x40022004: "FLASH_KEYR", 0x4002200C: "FLASH_SR",
    0x40022010: "FLASH_CR", 0x40022014: "FLASH_AR",
    0x40005400: "I2C1 base", 0x40005410: "I2C1_DR", 0x40005414: "I2C1_SR1", 0x40005555: "0x40005400+0x155?",
    0x40012400: "ADC1 base", 0x40012404: "ADC1_CR?", 0x4001244C: "ADC1 offset 0x4C",
    0x40003000: "??? (0x5555 cmd)", 0x40003004: "?? offset4", 0x40003008: "?? offset8", 0x4000300C: "?? offset0xC",
    0x40000400: "???", 0x40001000: "TIM2?", 0x40001400: "TIM3?", 0x40002000: "TIM5?",
    0x40004400: "USART2?", 0x40005000: "USART3?", 0x40007000: "USART5?",
    0x40013400: "GPIOE?", 0x40015000: "GPIO? 0x15000", 0x40015400: "GPIO? 0x15400",
    0x4001060E: "GPIOA offset?", 0x40020400: "CRC?",
    0xE000E010: "SysTick", 0xE000E100: "NVIC ISER",
    0x45670123: "FLASH KEY1", 0xCDEF89AB: "FLASH KEY2",
    0x20004128: "SRAM struct", 0x20004134: "SRAM struct+0xC",
}
w("=" * 78)
w("round28 —— 外设/Magic 常量引用点全表")
w("=" * 78)
w("")
for v, offs in sorted(occur.items(), key=lambda kv: -len(kv[1])):
    tag = KNOWN.get(v, "")
    w("0x%08X  x%-3d %s" % (v, len(offs), tag))
    w("      sites: %s" % ", ".join("0x%05X" % x for x in offs[:16]))
w("")
w("=" * 78)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("[saved] " + OUT)
