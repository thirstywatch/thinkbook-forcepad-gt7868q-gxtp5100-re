"""verify-B/scan1.py — 独立扫描 v2（修正映射方向）
file_offset = addr - 0x08005000 + 0x19ABC
"""
import sys, struct, collections
sys.path.insert(0, r"<WORKSPACE>")
from vdis import IMG, BASE_ADDR, BASE_OFF, disasm_range, md
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

TARG = {
    0x40005400: "I2C1", 0x40005800: "I2C2",
    0x40005C00: "I2C-5C00", 0x40006000: "I2C-6000", 0x40007000: "P-7000",
    0x40010800: "GPIOA", 0x40010C00: "GPIOB",
    0x40011000: "GPIOC", 0x40011400: "GPIOD",
    0x40011800: "GPIOE", 0x40011C00: "GPIOF", 0x40012000: "GPIOG",
    0x40013000: "SPI1", 0x40003800: "SPI2", 0x40003C00: "SPI3",
    0x40013800: "USART1", 0x40004400: "USART2", 0x40004800: "USART3",
    0x40020000: "DMA1", 0x40020400: "DMA2",
    0x40010000: "AFIO", 0x40021000: "RCC", 0x40022000: "FLASH",
    0x40012400: "ADC1", 0x40012800: "ADC2", 0x40012C00: "ADC3",
}
PERIPH_LO, PERIPH_HI = 0x40000000, 0x4003FFFF

ALL = disasm_range(BASE_ADDR, 0x08012C9F)
SEG_LO_OFF, SEG_HI_OFF = BASE_OFF, BASE_OFF + (0x08012C9F - BASE_ADDR)

print("=" * 74)
print("[A] 外设区地址（0x40000000-0x4003FFFF）作为 32 位 LE 出现在文件中的位置")
hits = collections.defaultdict(list)
for o in range(0, len(IMG.data) - 3):
    v = struct.unpack_from("<I", IMG.data, o)[0]
    if PERIPH_LO <= v <= PERIPH_HI:
        hits[v].append(o)
print("  不同取值 %d 个" % len(hits))
for v in sorted(hits):
    locs = sorted(hits[v])
    tag = TARG.get(v, "")
    segmark = lambda o: "SEG" if SEG_LO_OFF <= o <= SEG_HI_OFF else "out"
    print("  0x%08X %-9s x%-3d %s" % (v, tag, len(locs),
          " ".join("f%05X(%s)" % (o, segmark(o)) for o in locs[:10])))

print()
print("=" * 74)
print("[B] movw/movt 构造出的 32 位常量落在外设区")
pend = {}
for ins in ALL:
    if ins.mnemonic in ("movw", "movt") and len(ins.operands) == 2 and \
       ins.operands[1].type == ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg)
        v = ins.operands[1].imm
        if ins.mnemonic == "movw":
            pend[r] = (ins.address, v & 0xFFFF)
        else:
            if r in pend:
                a0, lo = pend[r]
                full = (lo | (v << 16)) & 0xFFFFFFFF
                if PERIPH_LO <= full <= PERIPH_HI:
                    print("  %08X/%08X %-3s -> 0x%08X %s" % (a0, ins.address, r, full, TARG.get(full, "")))
                del pend[r]

print()
print("=" * 74)
print("[C] ldr rX,[pc,#imm] 装入的外设区地址")
for ins in ALL:
    if ins.mnemonic != "ldr" or len(ins.operands) != 2:
        continue
    o0, o1 = ins.operands
    if o0.type != ARM_OP_REG or o1.type != ARM_OP_MEM:
        continue
    m = o1.mem
    if not m.base or ins.reg_name(m.base) != "pc":
        continue
    va = ((ins.address + 4) & ~3) + m.disp
    v = IMG.read32(va)
    if v is not None and PERIPH_LO <= v <= PERIPH_HI:
        print("  %08X  ldr %s,[pc,#%d] 池@%08X = 0x%08X %s" %
              (ins.address, ins.reg_name(o0.reg), m.disp, va, v, TARG.get(v, "")))
