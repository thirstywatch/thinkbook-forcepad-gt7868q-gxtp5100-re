# find_lra.py - 通过"设备结构体+4 持有外设基址"这一精确锚点，定位运行时定时器/GPIO 访问
import struct, capstone, collections

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
IMG_END = BASE + (len(data) - VOFF)
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True
def foff(a): return VOFF + (a - BASE)

# 初始化代码里出现的外设基址存放位置（结构体+字段偏移）
ANCHORS = {
    0x20004054: 'struct@0x20004050 +4   (init: 0x0800F0B5)',
    0x20004074: 'struct@0x20004070 +4   (init: 0x08005DE1)',
    0x200040BC: 'struct@0x200040B8 +4   (init: TIM2 0x40000000)',
    0x200040C0: 'struct@0x200040B8 +8   (init: 119)',
    0x200040C4: 'struct@0x200040B8 +12  (init: 1999)',
    0x2000412C: 'struct@0x20004128 +4',
    0x20004140: 'struct@0x20004128 +0x18',
    0x20004144: 'struct@0x20004128 +0x1C',
}

TIMOFF = {0x00:'CR1',0x04:'CR2',0x08:'SMCR',0x0C:'DIER',0x10:'SR',0x14:'EGR',0x18:'CCMR1',
          0x1C:'CCMR2',0x20:'CCER',0x24:'CNT',0x28:'PSC',0x2C:'ARR',0x30:'RCR',
          0x34:'CCR1',0x38:'CCR2',0x3C:'CCR3',0x40:'CCR4',0x44:'BDTR'}
GPIOOFF = {0x00:'CRL',0x04:'CRH',0x08:'IDR',0x0C:'ODR',0x10:'BSRR',0x14:'BRR'}

# 1) 找出所有引用这些 SRAM 锚点地址的指令（movw/movt 立即数 或 常量池）
hits = []
for ins in md.disasm(data[VOFF+0x140:], BASE+0x140):
    if ins.id == 0: continue
    try: ops = ins.operands
    except Exception: continue
    for op in ops:
        if op.type == capstone.arm.ARM_OP_MEM and ins.reg_name(op.mem.base) == 'pc':
            lit = ((ins.address+4)&0xFFFFFFFC) + op.mem.disp
            if BASE <= lit < IMG_END-3:
                v = struct.unpack_from('<I', data, foff(lit))[0]
                if v in ANCHORS:
                    hits.append((ins.address, lit, v))
    if ins.mnemonic in ('mov','mov.w','movs') and len(ops) == 2 and ops[1].type == capstone.arm.ARM_OP_IMM:
        if ops[1].imm in ANCHORS:
            hits.append((ins.address, None, ops[1].imm))

print('=== 引用设备结构体字段的位置 ===')
for a, lit, v in hits:
    print('  0x%08X  %s  (lit@0x%X)' % (a, ANCHORS[v], lit if lit else -1))

# 2) 在引用点附近的代码里寻找对外设偏移的访问
REGNAMES = {0x40000000:'TIM2',0x40000400:'TIM3',0x40000800:'TIM4',0x40000C00:'TIM5',
            0x40012C00:'TIM1',0x40013400:'TIM8',0x40010800:'GPIOA',0x40010C00:'GPIOB',
            0x40011000:'GPIOC',0x40005400:'I2C1'}
print('\n=== 引用点附近 ±0x60 字节内的访存指令 ===')
seen = set()
for a, lit, v in hits:
    lo, hi = a-0x60, a+0x60
    for ins in md.disasm(data[foff(lo):foff(lo)+(hi-lo)], lo):
        if ins.id == 0: continue
        if ins.mnemonic.startswith('str') or ins.mnemonic.startswith('ldr'):
            key = (ins.address, ins.mnemonic, ins.op_str)
            if key in seen: continue
            seen.add(key)
            try: ops = ins.operands
            except Exception: continue
            for op in ops:
                if op.type == capstone.arm.ARM_OP_MEM and 0 <= op.mem.disp <= 0x50 and op.mem.disp % 4 == 0:
                    nm = TIMOFF.get(op.mem.disp) or GPIOOFF.get(op.mem.disp) or ''
                    if nm:
                        print('    [锚点 0x%08X] 0x%08X  %-8s %-28s %s' % (a, ins.address, ins.mnemonic, ins.op_str, nm))
