# fw_periph2.py — 精细外设映射：按精确基址+寄存器偏移统计，并识别各外设用途
import struct, collections, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
code = data[VOFF + 0x140:]

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True

# 外设基址 -> 名称（STM32F1/GD32F30x 映射）
PERIPH = {
    0x40010000: 'AFIO', 0x40010400: 'EXTI', 0x40010800: 'GPIOA', 0x40010C00: 'GPIOB',
    0x40011000: 'GPIOC', 0x40011400: 'GPIOD', 0x40011800: 'GPIOE',
    0x40012400: 'ADC1', 0x40012800: 'ADC2', 0x40000000: 'TIM2', 0x40000400: 'TIM3',
    0x40000800: 'TIM4', 0x40000C00: 'TIM5', 0x40001000: 'TIM6', 0x40001400: 'TIM7',
    0x40010000+0x3400: 'TIM8?', 0x40012C00: 'TIM1', 0x40013400: 'TIM8',
    0x40005400: 'I2C1', 0x40005800: 'I2C2', 0x40003800: 'SPI2', 0x40013000: 'SPI1',
    0x40004400: 'USART2', 0x40004800: 'USART3', 0x40004C00: 'UART4', 0x40005000: 'UART5',
    0x40021000: 'RCC', 0x40022000: 'FLASH', 0x40007000: 'PWR', 0x40006C00: 'BKP',
    0x40020000: 'DMA1', 0x40020400: 'DMA2', 0xE000E000: 'SysTick/NVIC', 0xE000ED00: 'SCB',
    0x40005C00: 'USB', 0x40006400: 'CAN2', 0x40006000: 'CAN1', 0x40006C00+0x0: 'BKP',
}
REGOFF = {
    'GPIOx': {0x00:'CRL',0x04:'CRH',0x08:'IDR',0x0C:'ODR',0x10:'BSRR',0x14:'BRR',0x18:'LCKR'},
    'TIMx': {0x00:'CR1',0x04:'CR2',0x08:'SMCR',0x0C:'DIER',0x10:'SR',0x14:'EGR',0x18:'CCMR1',
             0x1C:'CCMR2',0x20:'CCER',0x24:'CNT',0x28:'PSC',0x2C:'ARR',0x30:'RCR',
             0x34:'CCR1',0x38:'CCR2',0x3C:'CCR3',0x40:'CCR4',0x44:'BDTR',0x48:'DCR',0x4C:'DMAR'},
    'I2Cx': {0x00:'CR1',0x04:'CR2',0x08:'OAR1',0x0C:'OAR2',0x10:'DR',0x14:'SR1',0x18:'SR2',0x1C:'CCR',0x20:'TRISE'},
    'ADCx': {0x00:'SR',0x04:'CR1',0x08:'CR2',0x0C:'SMPR1',0x10:'SMPR2',0x14:'JOFR1',0x4C:'DR'},
}

regs = {}
acc = collections.defaultdict(lambda: collections.Counter())
ex = collections.defaultdict(list)
n = 0

for ins in md.disasm(code, BASE + 0x140):
    n += 1
    if ins.id == 0:
        continue
    try:
        ops = ins.operands
    except Exception:
        continue
    m = ins.mnemonic
    if m in ('movw', 'movt') and len(ops) >= 2 and ops[0].type == capstone.arm.ARM_OP_REG and ops[1].type == capstone.arm.ARM_OP_IMM:
        r = ins.reg_name(ops[0].reg)
        v = ops[1].imm & 0xFFFF
        regs[r] = v if m == 'movw' else ((regs.get(r, 0) & 0xFFFF) | (v << 16))
        continue
    for op in ops:
        if op.type == capstone.arm.ARM_OP_MEM:
            b = ins.reg_name(op.mem.base)
            if b in regs:
                a = (regs[b] + op.mem.disp) & 0xFFFFFFFF
                if 0x40000000 <= a < 0x60000000:
                    base = None
                    for pb in PERIPH:
                        if pb <= a < pb + 0x400:
                            base = pb
                            break
                    if base is not None:
                        acc[base][a - base] += 1
                        if len(ex[base]) < 3:
                            ex[base].append('0x%08X: %s %s' % (ins.address, m, ins.op_str))
    try:
        _, written = ins.regs_access()
        for w in written:
            rn = ins.reg_name(w)
            if rn in regs:
                del regs[rn]
    except Exception:
        pass

print('反汇编 %d 条指令' % n)
print('\n=== 精确外设映射（基址 + 寄存器偏移访问次数）===')
for base, offs in sorted(acc.items(), key=lambda kv: -sum(kv[1].values())):
    name = PERIPH.get(base, '?')
    fam = 'GPIOx' if name.startswith('GPIO') else ('TIMx' if name.startswith('TIM') else ('I2Cx' if name.startswith('I2C') else ('ADCx' if name.startswith('ADC') else None)))
    total = sum(offs.values())
    print('\n  %s  0x%08X   共 %d 次' % (name, base, total))
    for off, cnt in offs.most_common(12):
        rn = REGOFF.get(fam, {}).get(off, '') if fam else ''
        print('      +0x%02X %-6s %3d 次' % (off, rn, cnt))
    if ex[base]:
        print('      例: ' + ' | '.join(ex[base]))
