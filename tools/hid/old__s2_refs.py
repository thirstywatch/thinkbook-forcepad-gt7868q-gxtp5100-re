"""步骤2：全镜像搜索对 I2C1 (0x40005400-0x40005423) 的任何引用。
(A) 数据里的字面量池字
(B) movw/movt 拼装（扫描所有偶地址）
(C) 从字面量池 ldr 的引用点
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

data = seg()
I2C1 = 0x40005400
LO, HI = I2C1, I2C1 + 0x24

print("=== (A) 数据/字面量池里落在 0x40005400-0x40005423 的 32 位字 ===")
hits = []
for o in range(0, len(data) - 3):
    w = int.from_bytes(data[o:o + 4], "little")
    if LO <= w < HI:
        # 是否 4 字节对齐
        hits.append((o, w))
for o, w in hits:
    print("  文件内偏移 0x%05X -> 地址 0x%08X : 字 0x%08X (偏移 +0x%02X)" % (o, SEG_LO + o, w, w - I2C1))
print("  合计 %d 处" % len(hits))

print("\n=== (B) movw/movt 拼装 I2C1 基址（全偶地址扫描，非递归下降）===")
m = md()
mm = []
for o in range(0, len(data) - 7, 2):
    a = SEG_LO + o
    i = insn_at(m, data, a)
    if i is None or i.mnemonic not in ("movw", "movt"):
        continue
    ops = i.op_str
    mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", ops)
    if not mt:
        continue
    reg, val = mt.group(1), int(mt.group(2), 16)
    j = insn_at(m, data, a + 4)
    if j is None or j.mnemonic not in ("movw", "movt"):
        continue
    m2 = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", j.op_str)
    if not m2 or m2.group(1) != reg:
        continue
    val2 = int(m2.group(2), 16)
    if i.mnemonic == "movw":
        full = (val2 << 16) | val
    else:
        full = (val << 16) | val2
    if LO <= full < HI:
        mm.append((a, i.mnemonic, full))
for a, mn, full in mm:
    print("  0x%08X: %s/movt -> 0x%08X" % (a, mn, full))
print("  合计 %d 处" % len(mm))

# 顺便统计所有出现的外设基址（宽范围），确认没有 I2C2/SPI
print("\n=== (B2) 全镜像 movw/movt 拼出的 0x4xxxxxxx / 0xExxxxxxx 常量统计 ===")
cnt = collections.Counter()
det = collections.defaultdict(list)
NAME = {
    0x40005400: "I2C1", 0x40005800: "I2C2", 0x40013000: "SPI1", 0x40003800: "SPI2",
    0x40003C00: "SPI3", 0x40013800: "USART1", 0x40004400: "USART2", 0x40004800: "USART3",
    0x40010800: "GPIOA", 0x40010C00: "GPIOB", 0x40011000: "GPIOC", 0x40011400: "GPIOD",
    0x40011800: "GPIOE", 0x40020000: "DMA1", 0x40020400: "DMA2", 0x40021000: "RCC",
    0x40022000: "FLASH", 0xE000E000: "SCB", 0xE000ED00: "SCB2", 0x40010000: "AFIO",
    0x40010400: "EXTI", 0x40012400: "ADC1", 0x40012C00: "TIM1", 0x40000000: "TIM2",
}
seen = set()
for o in range(0, len(data) - 7, 2):
    a = SEG_LO + o
    if a in seen:
        continue
    i = insn_at(m, data, a)
    if i is None or i.mnemonic not in ("movw",):
        continue
    mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", i.op_str)
    if not mt:
        continue
    reg, val = mt.group(1), int(mt.group(2), 16)
    j = insn_at(m, data, a + 4)
    if j is None or j.mnemonic != "movt":
        continue
    m2 = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", j.op_str)
    if not m2 or m2.group(1) != reg:
        continue
    full = (int(m2.group(2), 16) << 16) | val
    if (0x40000000 <= full < 0x60000000) or (0xE0000000 <= full < 0xE0100000):
        cnt[full] += 1
        det[full].append(a)
        seen.add(a)
for v, n in sorted(cnt.items()):
    print("  0x%08X %-12s x%-3d 首见 0x%08X" % (v, NAME.get(v, "?"), n, det[v][0]))

print("\n=== (B3) 任何落在 0x40005400-0x40005423 的 movw 立即数（单条，可能配 add）===")
for o in range(0, len(data) - 3, 2):
    a = SEG_LO + o
    i = insn_at(m, data, a)
    if i is None:
        continue
    if i.mnemonic == "movw":
        mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", i.op_str)
        if mt and 0x5400 <= int(mt.group(2), 16) <= 0x5423:
            print("  0x%08X: %s" % (a, i.mnemonic + " " + i.op_str))
    if i.mnemonic == "mov" or i.mnemonic == "movs":
        mt = re.match(r"(r\d+),\s*#(0x[0-9a-fA-F]+)", i.op_str)
        if mt and 0x5400 <= int(mt.group(2), 16) <= 0x5423:
            print("  0x%08X: %s" % (a, i.mnemonic + " " + i.op_str))
