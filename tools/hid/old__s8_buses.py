"""步骤8：Q4/Q5/Q3 机械检查
(1) 整个容器文件里 0x40005400 及其偏移是否出现（排除 TF100A 段之外还有别的镜像）
(2) GPIO 基址出现点 + 对 GPIO ODR/BSRR/BRR 的写点（找 bit-bang 迹象）
(3) DMA 使用点、CPAR 写点
(4) USART1 / SPI 使用点
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

FULL = open(BIN, "rb").read()
data = seg()
m = md()

print("=== (1) 整个容器(161628 B)里出现 0x40005400-0x40005423 的位置 ===")
n = 0
for o in range(0, len(FULL) - 3):
    w = int.from_bytes(FULL[o:o + 4], "little")
    if 0x40005400 <= w <= 0x40005423:
        inrange = FILE_OFF <= o < FILE_OFF + len(data)
        print("  文件偏移 0x%05X 字 0x%08X  %s" % (o, w, "在 TF100A 段内" if inrange else "★TF100A 段外"))
        n += 1
print("  合计 %d" % n)

# 整个容器里的 movw/movt 常量化（按 TF100A 映射解码）不适用，改为在 TF100A 段内做
# 下面 (2)(3)(4) 都基于 TF100A 段。
def const_before(addr, reg, maxn=25):
    a = addr - 2
    for _ in range(maxn):
        if a < SEG_LO:
            return None
        i = insn_at(m, data, a)
        if i is None:
            a -= 2
            continue
        if i.mnemonic == "movw" and i.op_str.startswith(reg + ","):
            mm = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)", i.op_str)
            lo = int(mm.group(1), 16)
            j = insn_at(m, data, a + 4)
            if j and j.mnemonic == "movt" and j.op_str.startswith(reg + ","):
                mm2 = re.match(r"r\d+,\s*#(0x[0-9a-fA-F]+)", j.op_str)
                return (int(mm2.group(1), 16) << 16) | lo
            return lo
        if re.match(r"^%s\s*," % reg, i.op_str):
            return None
        a -= i.size
    return None

NAME = {0x40010800: "GPIOA", 0x40010C00: "GPIOB", 0x40011000: "GPIOC", 0x40011400: "GPIOD",
        0x40011800: "GPIOE", 0x40020000: "DMA1", 0x40020400: "DMA2", 0x40013800: "USART1",
        0x40013000: "SPI1", 0x40003800: "SPI2", 0x40003C00: "SPI3", 0x40005800: "I2C2"}

print("\n=== (2)/(3)/(4) TF100A 段内对 GPIO/DMA/USART/SPI 寄存器的 store（基址回溯）===")
groups = collections.defaultdict(list)
for o in range(0, len(data) - 3, 2):
    a = SEG_LO + o
    i = insn_at(m, data, a)
    if i is None or not i.mnemonic.startswith("str"):
        continue
    mm = re.match(r"(r\d+),\s*\[(r\d+)([^\]]*)\]", i.op_str)
    if not mm:
        continue
    base_reg, rest = mm.group(2), mm.group(3).strip()
    if base_reg in ("sp", "pc"):
        continue
    off = None
    mo = re.match(r",\s*#(0x[0-9a-fA-F]+)", rest)
    if rest == "":
        off = 0
    elif mo:
        off = int(mo.group(1), 16)
    else:
        continue
    v = const_before(a, base_reg)
    if v is None:
        continue
    nm = NAME.get(v)
    if nm is None:
        continue
    val = mm.group(1)
    groups[nm].append((a, off, val, i.mnemonic))

for nm in ("GPIOA", "GPIOB", "GPIOC", "GPIOD", "GPIOE", "DMA1", "DMA2", "USART1", "SPI1", "SPI2", "SPI3", "I2C2"):
    g = groups.get(nm, [])
    print("  [%s] store 点数 = %d" % (nm, len(g)))
    for a, off, val, mn in g[:40]:
        print("     0x%08X  %-6s %s,[+0x%02X]" % (a, mn, val, off or 0))
    if len(g) > 40:
        print("     ...(%d more)" % (len(g) - 40))

print("\n=== GPIO ODR/BSRR/BRR 写点（bit-bang 迹象：同一函数内 ≥4 次翻转）===")
pat = collections.defaultdict(list)
for nm in ("GPIOA", "GPIOB", "GPIOC", "GPIOD", "GPIOE"):
    for a, off, val, mn in groups.get(nm, []):
        if off in (0x0C, 0x10, 0x14):
            pat[nm].append(a)
for nm, lst in pat.items():
    print("  %s: %d 次 -> %s" % (nm, len(lst), ", ".join("0x%08X" % x for x in lst[:30])))
