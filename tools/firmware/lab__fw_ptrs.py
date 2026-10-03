# fw_ptrs.py — 追踪「外设基址被缓存进 RAM 指针」的情形，重建真实外设映射并定位候选驱动函数
import struct, collections, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
CSTART = BASE + 0x140
code = data[VOFF + 0x140:]
IMG_END = BASE + (len(data) - VOFF)

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True

def rd32(a):
    if not (BASE <= a < IMG_END - 3):
        return None
    return struct.unpack_from('<I', data, VOFF + (a - BASE))[0]

NAMES = {0x40000000:'TIM2',0x40000400:'TIM3',0x40000800:'TIM4',0x40000C00:'TIM5',0x40001000:'TIM6',0x40001400:'TIM7',
 0x40010000:'AFIO',0x40010400:'EXTI',0x40010800:'GPIOA',0x40010C00:'GPIOB',0x40011000:'GPIOC',0x40011400:'GPIOD',
 0x40011800:'GPIOE',0x40011C00:'GPIOF',0x40012000:'ADC1',0x40012400:'ADC1r',0x40012C00:'TIM1',0x40013400:'TIM8',
 0x40003800:'SPI2',0x40013000:'SPI1',0x40004400:'USART2',0x40004800:'USART3',0x40004C00:'UART4',0x40005000:'UART5',
 0x40005400:'I2C1',0x40005800:'I2C2',0x40020000:'DMA1',0x40020400:'DMA2',0x40021000:'RCC',0x40022000:'FLASH',
 0x40007000:'PWR',0x40006C00:'BKP',0x40005C00:'USB',0x40006000:'CAN',0x40003000:'IWDG',0x40003400:'SPI2b',
 0xE000E100:'NVIC_ISER',0xE000E000:'SCB',0xE000ED00:'SCB2'}
def which(a):
    best = None
    for pb in NAMES:
        if pb <= a < pb + 0x400 and (best is None or pb > best):
            best = pb
    return best

# ---- Pass 1: 找「外设基址 -> 存入 SRAM 全局」的赋值 ----
sram_map = {}          # sram addr -> peripheral base
regs = {}
for ins in md.disasm(code, CSTART):
    if ins.id == 0: continue
    try: ops = ins.operands
    except Exception: continue
    m = ins.mnemonic
    if m in ('movw','movt') and len(ops)>=2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_IMM:
        r = ins.reg_name(ops[0].reg); v = ops[1].imm & 0xFFFF
        regs[r] = v if m=='movw' else ((regs.get(r,0)&0xFFFF)|(v<<16))
        continue
    if m in ('ldr','ldr.w') and len(ops)==2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_MEM and ins.reg_name(ops[1].mem.base)=='pc':
        v = rd32(((ins.address+4)&0xFFFFFFFC)+ops[1].mem.disp)
        if v is not None: regs[ins.reg_name(ops[0].reg)] = v
        continue
    # str rX, [rY, #imm]  其中 rX 是外设基址、rY+imm 在 SRAM
    if m.startswith('str') and len(ops)==2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_MEM:
        src = ins.reg_name(ops[0].reg); b = ins.reg_name(ops[1].mem.base)
        if src in regs and b in regs:
            dst = (regs[b] + ops[1].mem.disp) & 0xFFFFFFFF
            v = regs[src]
            if 0x20000000 <= dst < 0x20010000 and 0x40000000 <= v < 0x50000000:
                sram_map[dst] = v
    try:
        _, wr = ins.regs_access()
        for w in wr:
            rn = ins.reg_name(w)
            if rn in regs: del regs[rn]
    except Exception: pass

print('=== Pass1: 发现 %d 个「外设基址存入 SRAM」的全局指针 ===' % len(sram_map))
cnt = collections.Counter(sram_map.values())
for pb, c in cnt.most_common(30):
    print('   0x%08X (%s) 被缓存到 %d 个 SRAM 位置' % (pb, NAMES.get(pb,'?'), c))

# ---- Pass 2: 重新扫描，顺着这些 SRAM 全局解析外设访问 ----
regs = {}
acc = collections.defaultdict(collections.Counter)
owner = collections.defaultdict(set)
bl = set()
instrs = []
for ins in md.disasm(code, CSTART):
    if ins.id == 0: continue
    try: ops = ins.operands
    except Exception: continue
    m = ins.mnemonic; a = ins.address
    if m in ('movw','movt') and len(ops)>=2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_IMM:
        r = ins.reg_name(ops[0].reg); v = ops[1].imm & 0xFFFF
        regs[r] = v if m=='movw' else ((regs.get(r,0)&0xFFFF)|(v<<16))
        instrs.append((a,m,ins.op_str,None)); continue
    if m in ('ldr','ldr.w') and len(ops)==2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_MEM and ins.reg_name(ops[1].mem.base)=='pc':
        v = rd32(((a+4)&0xFFFFFFFC)+ops[1].mem.disp)
        if v is not None: regs[ins.reg_name(ops[0].reg)] = v
        instrs.append((a,m,ins.op_str,None)); continue
    if m.startswith('bl'):
        for op in ops:
            if op.type == capstone.arm.ARM_OP_IMM: bl.add(op.imm)
    hit = None
    for op in ops:
        if op.type == capstone.arm.ARM_OP_MEM:
            b = ins.reg_name(op.mem.base)
            if b in regs:
                addr = (regs[b] + op.mem.disp) & 0xFFFFFFFF
                # 直接外设访问，或经由 SRAM 指针
                pb = which(addr)
                if pb is not None:
                    acc[pb][addr - pb] += 1
                    hit = '%s+0x%X' % (NAMES.get(pb,'?'), addr-pb)
                elif addr in sram_map:
                    pb2 = sram_map[addr]
                    acc[pb2][0] += 1
                    hit = '%s(经RAM指针)' % NAMES.get(pb2,'?')
    instrs.append((a,m,ins.op_str,hit))
    if m in ('ldr','ldr.w') and len(ops)==2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_MEM:
        b = ins.reg_name(ops[1].mem.base)
        if b in regs:
            addr = (regs[b] + ops[1].mem.disp) & 0xFFFFFFFF
            if addr in sram_map:
                regs[ins.reg_name(ops[0].reg)] = sram_map[addr]
    try:
        _, wr = ins.regs_access()
        for w in wr:
            rn = ins.reg_name(w)
            if rn in regs and regs[rn] < 0x40000000:
                del regs[rn]
    except Exception: pass

print('\n=== Pass2: 重建后的外设映射 ===')
for pb, offs in sorted(acc.items(), key=lambda kv: -sum(kv[1].values())):
    print('  %-10s 0x%08X 共 %3d 次   偏移: %s' % (NAMES.get(pb,'?'), pb, sum(offs.values()),
          ' '.join('+0x%X(%d)' % (o,c) for o,c in offs.most_common(8))))

# 函数归属 + 调用者
INTEREST = [pb for pb in acc if NAMES.get(pb,'').startswith(('TIM','GPIO','SPI','ADC','I2C1','USART'))]
func = None
func_hits = collections.defaultdict(set)
for (a,m,os_,hit) in instrs:
    if a in bl or func is None: func = a
    if hit: func_hits[func].add(hit)
callers = collections.defaultdict(list)
for (a,m,os_,hit) in instrs:
    if m.startswith('bl') and '#' in os_:
        try: callers[int(os_.strip().lstrip('#'),16)].append(a)
        except Exception: pass
print('\n=== 访问 TIM/GPIO/SPI/ADC/I2C/USART 的函数（候选驱动）===')
for f, hits in sorted(func_hits.items(), key=lambda kv: -len(kv[1]))[:14]:
    cl = callers.get(f, [])
    print('  0x%08X : %s' % (f, ' '.join(sorted(hits)[:8])))
    print('        调用者 %d 个: %s' % (len(cl), ' '.join('0x%X'%c for c in cl[:8])))
