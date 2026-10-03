# vib_transport.py — 1) 向量表全景（哪些 ISR 在镜像内/缺失）2) I2C1 是主机还是从机？地址是多少？
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
out = io.open(r"<LAB>\touchpad-lab\re\vib_transport_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

IRQ = {0: "WWDG", 1: "PVD", 2: "TAMPER", 3: "RTC", 4: "FLASH", 5: "RCC", 6: "EXTI0", 7: "EXTI1",
       8: "EXTI2", 9: "EXTI3", 10: "EXTI4", 11: "DMA1_CH1", 12: "DMA1_CH2", 13: "DMA1_CH3",
       14: "DMA1_CH4", 15: "DMA1_CH5", 16: "DMA1_CH6", 17: "DMA1_CH7", 18: "ADC1_2",
       19: "CAN1_TX", 20: "CAN1_RX0", 21: "CAN1_RX1", 22: "CAN1_SCE", 23: "EXTI9_5",
       24: "TIM1_BRK", 25: "TIM1_UP", 26: "TIM1_TRG_COM", 27: "TIM1_CC", 28: "TIM2",
       29: "TIM3", 30: "TIM4", 31: "I2C1_EV", 32: "I2C1_ER", 33: "I2C2_EV", 34: "I2C2_ER",
       35: "SPI1", 36: "SPI2", 37: "USART1", 38: "USART2", 39: "USART3", 40: "EXTI15_10",
       41: "RTCAlarm", 42: "USB_FS_WKUP", 43: "TIM8_BRK", 44: "TIM8_UP", 45: "TIM8_TRG_COM",
       46: "TIM8_CC", 47: "ADC3", 48: "FSMC", 49: "SDIO", 50: "TIM5", 51: "SPI3", 52: "UART4",
       53: "UART5", 54: "TIM6", 55: "TIM7", 56: "DMA2_CH1", 57: "DMA2_CH2", 58: "DMA2_CH3",
       59: "DMA2_CH4_5"}

P("=== 向量表（镜像内前 256 字节）===")
sp = struct.unpack_from("<I", img, 0)[0]
P("  初始 SP = 0x%08X" % sp)
entries = []
for slot in range(1, 64):
    v = struct.unpack_from("<I", img, slot * 4)[0]
    entries.append((slot, v))
for slot, v in entries:
    inside = BASE <= (v & ~1) < END
    nm = "IRQ%d %s" % (slot - 16, IRQ.get(slot - 16, "?")) if slot >= 16 else "core#%d" % slot
    P("  slot %2d  %-14s -> 0x%08X  %s" % (slot, nm, v, "in" if inside else "★OUT (缺失尾部)"))

# ---- I2C1 初始化：看是否写 OAR1/OAR2（从机地址） ----
def show(a, b, title):
    P("\n===== %s [0x%08X..0x%08X] =====" % (title, a, b))
    for i in allins:
        if a <= i.address < b:
            P("  %08X: %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

# I2C1 基址 0x40005400 首次出现在 0x0800394E 一簇：把整个函数看全
lo = None
for i in allins:
    if i.address <= 0x0800394E:
        lo = i.address
show(0x080038C0, 0x08003A40, "I2C1 相关函数簇")
show(0x08008D00, 0x08008FA0, "USART1 相关函数簇 (0x08008D40 起)")
out.close()
print("done")
