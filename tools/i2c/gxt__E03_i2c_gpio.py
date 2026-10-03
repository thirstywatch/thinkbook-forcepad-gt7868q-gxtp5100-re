# -*- coding: utf-8 -*-
"""E03. ★★ I2C/GPIO 代码分析 —— 找触觉芯片(AW86927, I2C 0x5A/0x5B)的通信证据。
思路: 真 Thumb 代码里, 外设访问通常是:
  1) 先 ldr rX,[pc,#imm] 得到外设基址 (常量池), 再 str/ldr [rX,#off]
  2) 常量池里会直接出现 0x40005400 (I2C1), 0x40020000/0x48000000 (GPIO)
所以: 扫描代码区的常量池(literal pool)中所有 4 字节对齐值, 找外设地址。
同时: 扫描 movw/movt 组合。
关键: 若出现 0x5A/0x5B 作为"写入的数据", 且与外设基址同函数 -> 触觉线索。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
from collections import Counter
FW = load(); N = len(FW)

CODE_LO, CODE_HI = 0x19850, 0x265B8

print("=" * 100)
print("E03-a. ★ 代码区常量池 (literal pool) 中的 32-bit 值分类")
print("=" * 100)
# 收集所有指向代码区的 ldr rt,[pc,#imm] 的落点
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True
pool_addrs = set()
for i in range(CODE_LO, CODE_HI, 2):
    for ins in md.disasm(FW[i:i+4], i):
        if ins.size > 4: break
        if ins.mnemonic == "ldr" and len(ins.operands) == 2 \
           and ins.operands[0].type == ARM_OP_REG and ins.operands[1].type == ARM_OP_MEM \
           and ins.operands[1].mem.base == ARM_REG_PC:
            tgt = i + 4 + ins.operands[1].mem.disp
            if CODE_LO <= tgt < N - 4:
                pool_addrs.add(tgt)
        break
print(f"  PC 相对常量池落点数 = {len(pool_addrs)}")

vals = [le32(FW, a) for a in sorted(pool_addrs)]
fam = Counter()
interesting = []
for a, v in sorted(zip(sorted(pool_addrs), vals)):
    if 0x40000000 <= v < 0x60000000: fam["外设 0x40000000-0x5FFFFFFF"] += 1
    elif 0x20000000 <= v < 0x20080000: fam["RAM 0x20000000"] += 1
    elif 0x08000000 <= v < 0x08200000: fam["FLASH 0x08000000"] += 1
    elif 0xE0000000 <= v: fam["系统 0xE0000000+"] += 1
    elif v < 0x00030000: fam["小整数/低地址"] += 1
    else: fam["其它"] += 1
    if 0x40000000 <= v < 0x60000000 or 0x08000000 <= v < 0x08200000:
        interesting.append((a, v))
print(f"  常量池值分类: {dict(fam)}")
print(f"\n  ★ 外设/FLASH 基址类常量 (共 {len(interesting)} 个, 去重后):")
c = Counter(v for _, v in interesting)
for v, n in c.most_common(40):
    print(f"    0x{v:08X}  x{n}")

print("\n" + "=" * 100)
print("E03-b. ★★ 关键外设地址点名检查")
print("=" * 100)
targets = {
    "I2C1 基址 0x40005400": 0x40005400,
    "I2C1 CR1 0x40005400": 0x40005400, "I2C1 CCR 0x4000541C": 0x4000541C,
    "I2C1 TRISE 0x40005420": 0x40005420, "I2C1 DR 0x40005410": 0x40005410,
    "I2C1 SR1 0x40005414": 0x40005414, "I2C1 SR2 0x40005418": 0x40005418,
    "I2C1 OAR1 0x40005408": 0x40005408, "I2C1 OAR2 0x4000540C": 0x4000540C,
    "I2C2 基址 0x40005800": 0x40005800, "I2C3 基址 0x40005C00": 0x40005C00,
    "GPIOA 0x40020000": 0x40020000, "GPIOB 0x40020400": 0x40020400,
    "GPIOC 0x40020800": 0x40020800, "GPIOD 0x40020C00": 0x40020C00,
    "GPIOE 0x40021000": 0x40021000, "GPIOF 0x40021400": 0x40021400,
    "GPIOG 0x40021800": 0x40021800, "GPIOH 0x40021C00": 0x40021C00,
    "RCC 0x40023800": 0x40023800, "TIM1 0x40010000": 0x40010000,
    "TIM2 0x40000000": 0x40000000, "TIM3 0x40000400": 0x40000400,
    "TIM4 0x40000800": 0x40000800, "TIM5 0x40000C00": 0x40000C00,
    "DMA1 0x40026000": 0x40026000, "DMA2 0x40026400": 0x40026400,
    "SPI1 0x40013000": 0x40013000, "SPI2 0x40003800": 0x40003800,
    "USART1 0x40011000": 0x40011000, "USART2 0x40004400": 0x40004400,
    "ADC1 0x40012000": 0x40012000, "EXTI 0x40013C00": 0x40013C00,
    "SYSCFG 0x40013800": 0x40013800,
}
for name, addr in targets.items():
    # 在常量池值里找
    hits = [a for a in pool_addrs if le32(FW, a) == addr]
    # 也在全字节流里找(可能未对齐)
    raw = []
    st = 0
    pb = addr.to_bytes(4, "little")
    while True:
        k = FW.find(pb, st)
        if k < 0: break
        raw.append(k); st = k+1
    mark = "  <<<" if hits else ""
    print(f"  {name:26s} 常量池={len(hits):>3d} 任意位置={len(raw):>3d}{mark}")
    if hits:
        print(f"      常量池偏移: {[hex(h) for h in hits[:8]]}")

print("\n" + "=" * 100)
print("E03-c. ★★ I2C 从地址 0x5A/0x5B 在代码区作为立即数/数据出现")
print("=" * 100)
for val in (0x5A, 0x5B, 0x2D, 0x2C, 0x2E, 0x5C, 0x5D, 0x6A, 0x6B, 0xD4, 0xD6):
    # 1) 作为 movs rX,#imm
    cnt_mov = 0
    for i in range(CODE_LO, CODE_HI, 2):
        for ins in md.disasm(FW[i:i+2], i):
            if ins.size != 2: break
            if ins.mnemonic in ("movs","mov") and len(ins.operands)==2 \
               and ins.operands[1].type == ARM_OP_IMM and ins.operands[1].imm == val:
                cnt_mov += 1
            break
    # 2) 作为常量池值
    cnt_pool = sum(1 for a in pool_addrs if le32(FW, a) == val)
    cnt_pool16 = sum(1 for a in pool_addrs if le16(FW, a) == val)
    print(f"  imm=0x{val:02X} ({val:>3d}): movs 立即数={cnt_mov:>3d}  常量池u32={cnt_pool} u16={cnt_pool16}")

print("\n" + "=" * 100)
print("E03-d. ★★ 直接反汇编: 找写 I2C1 DR (0x40005410) 的代码上下文")
print("=" * 100)
# 先找常量池里含 0x40005400 的位置, 再看谁 ldr 它
i2c1_addrs = [a for a in pool_addrs if le32(FW, a) == 0x40005400]
print(f"  常量池含 0x40005400 的位置: {[hex(a) for a in i2c1_addrs]}")
for pa in i2c1_addrs:
    # 找引用该池的 ldr
    for i in range(max(CODE_LO, pa-0x1000), min(CODE_HI, pa+8), 2):
        for ins in md.disasm(FW[i:i+4], i):
            if ins.size > 4: break
            if ins.mnemonic == "ldr" and len(ins.operands) == 2 \
               and ins.operands[1].type == ARM_OP_MEM \
               and ins.operands[1].mem.base == ARM_REG_PC:
                tgt = i + 4 + ins.operands[1].mem.disp
                if tgt == pa:
                    print(f"    @0x{i:05X}: {ins.mnemonic} {ins.op_str}   (加载 I2C1 基址)")
            break
