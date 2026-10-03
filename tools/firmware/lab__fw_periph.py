# fw_periph.py — 扫描固件代码中引用的外设寄存器地址（重建外设映射）
import struct, collections, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF = 0x19ABC          # 镜像基址对应的文件偏移
BASE = 0x08000000
code = data[VOFF:]
print('代码区: file 0x%X..0x%X  ->  0x%08X..0x%08X  (%d 字节)' % (VOFF, len(data), BASE, BASE + len(code), len(code)))

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True          # 跳过向量表/常量池等非指令字节，不要中途停下

START = BASE + 0x140        # 跳过向量表
code = data[VOFF + 0x140:]
print('反汇编起点: 0x%08X (file 0x%X)' % (START, VOFF + 0x140))
for ins in md.disasm(code[:64], START):
    print('   0x%08X  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
print('   ...')

regs = {}
periph = collections.Counter()
examples = collections.defaultdict(list)
sram_refs = collections.Counter()
n_ins = 0

for ins in md.disasm(code, START):
    n_ins += 1
    if ins.id == 0:          # skipdata 伪指令（数据区/常量池）
        continue
    try:
        ops = ins.operands
    except Exception:
        continue
    m = ins.mnemonic
    ops = ins.operands

    if m in ('movw', 'movt') and len(ops) >= 2 and ops[0].type == capstone.arm.ARM_OP_REG and ops[1].type == capstone.arm.ARM_OP_IMM:
        r = ins.reg_name(ops[0].reg)
        v = ops[1].imm & 0xFFFF
        if m == 'movw':
            regs[r] = v
        else:
            regs[r] = (regs.get(r, 0) & 0xFFFF) | (v << 16)
        continue

    for op in ops:
        if op.type == capstone.arm.ARM_OP_MEM:
            b = ins.reg_name(op.mem.base)
            if b in regs:
                addr = (regs[b] + op.mem.disp) & 0xFFFFFFFF
                if 0x40000000 <= addr < 0x60000000:
                    blk = addr & 0xFFFFF000
                    periph[blk] += 1
                    if len(examples[blk]) < 2:
                        examples[blk].append('0x%08X: %s %s' % (ins.address, m, ins.op_str))
                elif 0x20000000 <= addr < 0x20010000:
                    sram_refs[addr & 0xFFFFF000] += 1

    # 指令写入了被跟踪的寄存器 -> 失效
    try:
        _, written = ins.regs_access()
        for w in written:
            rn = ins.reg_name(w)
            if rn in regs:
                del regs[rn]
    except Exception:
        pass

print('共反汇编 %d 条指令' % n_ins)
print('\n=== 代码引用的外设寄存器块（按引用次数）===')
for blk, cnt in periph.most_common(40):
    print('  0x%08X 区块  引用 %3d 次   %s' % (blk, cnt, ' | '.join(examples[blk])))

print('\n=== SRAM 使用区块（前 15）===')
for blk, cnt in sram_refs.most_common(15):
    print('  0x%08X  %d 次' % (blk, cnt))

# 已知 MCU 外设基址对照
known = {
    0x40000000: 'STM32F4: TIM2', 0x40000400: 'STM32F4: TIM3', 0x40000800: 'STM32F4: TIM4',
    0x40010000: 'STM32F4: TIM1', 0x40010400: 'STM32F4: TIM8',
    0x40005400: 'STM32F4: I2C1', 0x40005800: 'STM32F4: I2C2', 0x40005C00: 'STM32F4: I2C3',
    0x40020000: 'STM32F4: GPIOA', 0x40020400: 'STM32F4: GPIOB', 0x40020800: 'STM32F4: GPIOC',
    0x40023800: 'STM32F4: RCC', 0x40021000: 'STM32F1: RCC',
    0x48000000: 'STM32L4/G4/H7: GPIOA', 0x48000400: 'STM32L4/G4: GPIOB',
    0x50000000: 'STM32F0/L0: GPIOA', 0x40021000: 'STM32F1/L4: RCC',
}
print('\n=== 与已知 MCU 外设基址对照 ===')
for blk in periph:
    if blk in known:
        print('  0x%08X -> %s (引用 %d 次)' % (blk, known[blk], periph[blk]))
