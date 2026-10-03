import struct, re
BIN = r"<WORKSPACE>"
BASE_ADDR = 0x08005000
BASE_OFF  = 0x19ABC
blob = open(BIN,'rb').read()
def addr(o): return o - BASE_OFF + BASE_ADDR

# All STM32F1 peripheral bases we care about, as 32-bit LE words
targets = {
 0x40005400: "I2C1",
 0x40005800: "I2C2",
 0x40004400: "USART2", 0x40004800: "USART3", 0x40013800: "USART1",
 0x40010000: "AFIO", 0x40010400: "EXTI", 0x40010800: "GPIOA",
 0x40010C00: "GPIOB", 0x40011000: "GPIOC", 0x40011400: "GPIOD",
 0x40020000: "ADC1", 0x40003000: "SPI2?", 0x40003800: "SPI3?",
 0x40013000: "SPI1", 0x40000000: "TIM2", 0x40000400: "TIM3",
 0x40003C00: "SPI?", 0x40005000: "SPI?",
}
print("=== 32-bit LE word occurrences in whole file ===")
for val,name in sorted(targets.items()):
    pat = struct.pack('<I', val)
    hits = [m.start() for m in re.finditer(re.escape(pat), blob)]
    if hits:
        inrange = [h for h in hits if BASE_OFF <= h < BASE_OFF+56480]
        print(f"{name:8s} {val:#010x}  total={len(hits)}  inTF100A_seg={len(inrange)}")
        for h in inrange:
            print(f"    -> file {h:#08x}  ADDR {addr(h):#010x}")

print()
print("=== I2C base +/- small: any word 0x400054xx / 0x400058xx (direct reg addr) ===")
for o in range(0, len(blob)-4, 2):
    w = struct.unpack_from('<I', blob, o)[0]
    if (w & 0xFFFFFF00) in (0x40005400, 0x40005800):
        print(f"  file {o:#08x} ADDR {addr(o):#010x} = {w:#010x}")
