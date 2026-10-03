# vib_bus.py — 这颗芯片到底挂在什么总线上？（I2C 从机 / SPI 从机 / UART）+ LRA 播放回调反汇编
import re, struct, io
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
img = data[0x19ABC:]
BASE = 0x08000000
END = BASE + len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
allins = list(md.disasm(img, BASE))
out = io.open(r"<LAB>\touchpad-lab\re\vib_bus_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

PERIPH = {
    0x40013800: "USART1", 0x40004400: "USART2", 0x40004800: "USART3",
    0x40005400: "I2C1", 0x40005800: "I2C2", 0x40005C00: "I2C3",
    0x40013000: "SPI1", 0x40003800: "SPI2", 0x40003C00: "SPI3",
    0x40012400: "ADC1", 0x40012800: "ADC2",
    0x40010000: "TIM2", 0x40000400: "TIM3", 0x40000800: "TIM4",
    0x40012C00: "TIM5", 0x40001000: "TIM6", 0x40001400: "TIM7", 0x40013400: "TIM8",
    0x40020000: "DMA1", 0x40020400: "DMA2",
    0x40010800: "GPIOA", 0x40010C00: "GPIOB", 0x40011000: "GPIOC",
    0x40011400: "GPIOD", 0x40011800: "GPIOE",
    0x40021000: "RCC", 0x40022000: "FLASH", 0x40010400: "EXTI",
    0x40006C00: "BKP?", 0x40007000: "PWR?",
    0xE000E100: "NVIC", 0xE000E000: "SCS", 0xE000ED00: "SCB",
    0x1FFFF7E0: "UID/flashsize",
}

# ---- 1) movw/movt 配对还原完整地址 ----
P("=== 外设基址引用（movw/movt 配对 + 字面量） ===")
cnt = {}
pend = {}
for i in allins:
    m = re.match(r"^(\w+), #0x([0-9a-f]+)$", i.op_str)
    if not m:
        continue
    reg, val = m.group(1), int(m.group(2), 16)
    if i.mnemonic == "movw":
        pend[reg] = (val, i.address)
    elif i.mnemonic == "movt":
        if reg in pend:
            lo, at = pend.pop(reg)
            full = (val << 16) | lo
            if full in PERIPH:
                cnt.setdefault(full, []).append(at)
for v in sorted(cnt):
    P("  movw/movt 0x%08X %-10s %3d 次  首处 %s" % (v, PERIPH[v], len(cnt[v]), " ".join("%X" % x for x in cnt[v][:5])))

P("")
P("=== 字面量（4 字节）形式的外设基址 ===")
for v, nm in sorted(PERIPH.items()):
    pat = struct.pack("<I", v)
    hits = [m.start() for m in re.finditer(re.escape(pat), img)]
    if hits:
        P("  0x%08X %-10s 字面量 %d 处: %s" % (v, nm, len(hits), " ".join("%X" % (BASE + h) for h in hits[:6])))

# ---- 2) 0x0800A7FC：写 GPIOA 的"通知"函数 ----
def show(a, b, title):
    P("\n===== %s [0x%08X..0x%08X] =====" % (title, a, b))
    for i in allins:
        if a <= i.address < b:
            P("  %08X: %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

show(0x0800A7F0, 0x0800A830, "0x0800A7FC (GPIOA 通知？)")
show(0x0800D6E0, 0x0800D780, "ctx+0x14 播放回调 0x0800D6F4")
show(0x0800D850, 0x0800D900, "镜像末尾区 (调用越界目标)")

# ---- 3) TIM3/TIM2 寄存器绝对写入 ----
P("\n=== 谁在写 TIM3(0x40000400) / TIM2(0x40010000) 相关 ===")
for i in allins:
    if i.mnemonic in ("str", "strh", "strb") and ("0x40000400" in i.op_str or "0x40010000" in i.op_str):
        P("  %08X %s %s" % (i.address, i.mnemonic, i.op_str))

out.close()
print("done")
