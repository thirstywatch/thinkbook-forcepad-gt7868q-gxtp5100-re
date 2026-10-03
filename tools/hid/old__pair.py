"""verify-B/pair.py — 找 movw #LOW / movt #0x4000 的配对，还原被物化的外设基址"""
import struct, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
ALL = []
a = A_LO
while a <= A_HI:
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; break
    else:
        a += 2

NAMES = {
 0x40005400:"I2C1",0x40005800:"I2C2",0x40005C00:"I2C3?",0x40006000:"?6000",
 0x40010800:"GPIOA",0x40010C00:"GPIOB",0x40011000:"GPIOC",0x40011400:"GPIOD",
 0x40011800:"GPIOE",0x40013000:"SPI1",0x40003800:"SPI2",0x40013800:"USART1",
 0x40004400:"USART2",0x40004800:"USART3",0x40010000:"AFIO",0x40021000:"RCC",
 0x40022000:"FLASH",0x40020000:"DMA1",0x40020400:"DMA2",0x40012400:"ADC1",
 0x40012800:"ADC2",0x40012C00:"ADC3",0x40000000:"TIM2",0x40000400:"TIM3",
 0x40000800:"TIM4",0x40013400:"?",0x40003000:"?",0x40006400:"?6400",
 0x40006C00:"?6C00",0x40006800:"?6800",0x40022000:"FLASH",
}

# 记录每个寄存器的最后一次 movw
lastw = {}
pairs = []
for i, ins in enumerate(ALL):
    if ins.mnemonic == "movw" and len(ins.operands) == 2 and ins.operands[1].type == ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg)
        lastw[r] = (ins.address, ins.operands[1].imm & 0xFFFF, i)
    elif ins.mnemonic == "movt" and len(ins.operands) == 2 and ins.operands[1].type == ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg)
        hi = ins.operands[1].imm & 0xFFFF
        if r in lastw:
            wa, lo, wi = lastw[r]
            full = (lo | (hi << 16)) & 0xFFFFFFFF
            gap = i - wi
            pairs.append((ins.address, wa, r, full, gap))
            del lastw[r]
        else:
            pairs.append((ins.address, None, r, (hi << 16), None))

print("=" * 78)
print("[A] 所有 movw+movt 配对，按还原值分组（只列 0x40000000-0x4003FFFF）")
hits = collections.defaultdict(list)
for mt, mw, r, full, gap in pairs:
    if 0x40000000 <= full <= 0x4003FFFF:
        hits[full].append((mw, mt, r, gap))
for v in sorted(hits):
    hs = hits[v]
    tag = NAMES.get(v, "??")
    print("  0x%08X %-7s x%-2d  %s" % (v, tag, len(hs),
          " ".join("%s@%08X" % (("%08X"%mw) if mw else "----", mt) for mw, mt, r, g in hs[:10])))
if not hits:
    print("  (无)")

print()
print("=" * 78)
print("[B] movw #0x5400 的全部出现及其后续 6 条指令")
for ins in ALL:
    if ins.mnemonic == "movw" and len(ins.operands) == 2 and ins.operands[1].type == ARM_OP_IMM \
       and (ins.operands[1].imm & 0xFFFF) == 0x5400:
        print("  ---- movw #0x5400 @ %08X (r=%s)" % (ins.address, ins.reg_name(ins.operands[0].reg)))
        i = ALL.index(ins)
        for k in range(0, 7):
            if i + k < len(ALL):
                x = ALL[i+k]
                print("       %08X  %-8s %s" % (x.address, x.mnemonic, x.op_str))
