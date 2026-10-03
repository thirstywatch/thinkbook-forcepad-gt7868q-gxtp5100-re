# fw_ptrs2.py — 完整常量传播：mov.w 立即数 + 常量池 + 结构体字段(+4)持有的外设基址
# 目标：找出运行时对定时器寄存器的访问（尤其 CCER 开关 = 震动最可能的实现）
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
    if not (BASE <= a < IMG_END - 3): return None
    return struct.unpack_from('<I', data, VOFF + (a - BASE))[0]

NAME = {0x40000000:'TIM2',0x40000400:'TIM3',0x40000800:'TIM4',0x40000C00:'TIM5',0x40001000:'TIM6',0x40001400:'TIM7',
 0x40010000:'AFIO',0x40010400:'EXTI',0x40010800:'GPIOA',0x40010C00:'GPIOB',0x40011000:'GPIOC',0x40011400:'GPIOD',
 0x40011800:'GPIOE',0x40012000:'ADC1',0x40012400:'ADC1r',0x40012C00:'TIM1',0x40013400:'TIM8',0x40003800:'SPI2',
 0x40013000:'SPI1',0x40004400:'USART2',0x40004800:'USART3',0x40004C00:'UART4',0x40005000:'UART5',0x40005400:'I2C1',
 0x40005800:'I2C2',0x40020000:'DMA1',0x40020400:'DMA2',0x40021000:'RCC',0x40022000:'FLASH',0x40007000:'PWR',
 0x40006C00:'BKP',0x40005C00:'USB',0x40006000:'CAN',0x40003000:'IWDG'}
def which(a):
    best=None
    for pb in NAME:
        if pb <= a < pb+0x400 and (best is None or pb>best): best=pb
    return best

REGOFF = {'TIM':{0x00:'CR1',0x04:'CR2',0x08:'SMCR',0x0C:'DIER',0x10:'SR',0x14:'EGR',0x18:'CCMR1',0x1C:'CCMR2',
                 0x20:'CCER',0x24:'CNT',0x28:'PSC',0x2C:'ARR',0x30:'RCR',0x34:'CCR1',0x38:'CCR2',0x3C:'CCR3',0x40:'CCR4',0x44:'BDTR'},
          'GPIO':{0x00:'CRL',0x04:'CRH',0x08:'IDR',0x0C:'ODR',0x10:'BSRR',0x14:'BRR'},
          'ADC':{0x00:'SR',0x04:'CR1',0x08:'CR2',0x0C:'SMPR1',0x10:'SMPR2',0x30:'SQR2',0x34:'SQR3',0x38:'JSQR',0x4C:'DR'},
          'I2C':{0x00:'CR1',0x04:'CR2',0x08:'OAR1',0x0C:'OAR2',0x10:'DR',0x14:'SR1',0x18:'SR2',0x1C:'CCR',0x20:'TRISE'}}

def load_imm(ins):
    """返回 (目标寄存器名, 立即数) 或 None"""
    m = ins.mnemonic; ops = ins.operands
    if len(ops) >= 2 and ops[0].type == capstone.arm.ARM_OP_REG and ops[1].type == capstone.arm.ARM_OP_IMM:
        if m in ('mov','mov.w','movs','movw','add','adds','sub','subs','orr','orrs','and','ands','bic','bics','cmp','cmp.w'):
            return (ins.reg_name(ops[0].reg), ops[1].imm & 0xFFFFFFFF, m)
    return None

# ---------- Pass 1: 结构体字段 -> 外设基址 ----------
regs = {}
field_map = {}      # (struct_addr, offset) -> periph base
for ins in md.disasm(code, CSTART):
    if ins.id == 0: continue
    try: ops = ins.operands
    except Exception: continue
    got = load_imm(ins)
    if got and got[2] in ('mov','mov.w','movs','movw','movt'):
        r, v, m = got
        if m == 'movw': regs[r] = v & 0xFFFF
        elif m == 'movt': regs[r] = (regs.get(r,0) & 0xFFFF) | ((v & 0xFFFF) << 16)
        else: regs[r] = v
        continue
    if ins.mnemonic in ('ldr','ldr.w') and len(ops)==2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_MEM and ins.reg_name(ops[1].mem.base)=='pc':
        v = rd32(((ins.address+4)&0xFFFFFFFC)+ops[1].mem.disp)
        if v is not None: regs[ins.reg_name(ops[0].reg)] = v
        continue
    if ins.mnemonic.startswith('str') and len(ops)==2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_MEM:
        src = ins.reg_name(ops[0].reg); b = ins.reg_name(ops[1].mem.base)
        if src in regs and b in regs:
            dst = (regs[b] + ops[1].mem.disp) & 0xFFFFFFFF
            v = regs[src]
            if 0x20000000 <= dst < 0x20010000 and which(v) is not None:
                field_map[(dst & ~3, dst & 3)] = v
    try:
        _, wr = ins.regs_access()
        for w in wr:
            rn = ins.reg_name(w)
            if rn in regs: del regs[rn]
    except Exception: pass

print('=== Pass1: 结构体字段持有的外设基址 (%d 个) ===' % len(field_map))
for (sa, off), v in sorted(field_map.items()):
    print('   结构体 0x%08X +0x%X  ->  %s (0x%08X)' % (sa, off, NAME.get(v,'?'), v))

# ---------- Pass 2: 运行时访问 ----------
regs = {}
acc = collections.defaultdict(collections.Counter)
site = collections.defaultdict(list)
bl = set()
ins_all = []
for ins in md.disasm(code, CSTART):
    if ins.id == 0: continue
    try: ops = ins.operands
    except Exception: continue
    a = ins.address; m = ins.mnemonic
    got = load_imm(ins)
    if got and got[2] in ('mov','mov.w','movs','movw','movt'):
        r, v, mm = got
        if mm == 'movw': regs[r] = v & 0xFFFF
        elif mm == 'movt': regs[r] = (regs.get(r,0) & 0xFFFF) | ((v & 0xFFFF) << 16)
        else: regs[r] = v
        ins_all.append((a,m,ins.op_str,None,None)); continue
    if m in ('ldr','ldr.w') and len(ops)==2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_MEM and ins.reg_name(ops[1].mem.base)=='pc':
        v = rd32(((a+4)&0xFFFFFFFC)+ops[1].mem.disp)
        if v is not None: regs[ins.reg_name(ops[0].reg)] = v
        ins_all.append((a,m,ins.op_str,None,None)); continue
    if m.startswith('bl'):
        for op in ops:
            if op.type == capstone.arm.ARM_OP_IMM: bl.add(op.imm)
    # 结构体字段取基址
    if m in ('ldr','ldr.w') and len(ops)==2 and ops[0].type==capstone.arm.ARM_OP_REG and ops[1].type==capstone.arm.ARM_OP_MEM:
        b = ins.reg_name(ops[1].mem.base)
        if b in regs:
            addr = (regs[b] + ops[1].mem.disp) & 0xFFFFFFFF
            key = (addr & ~3, addr & 3)
            if key in field_map:
                regs[ins.reg_name(ops[0].reg)] = field_map[key]
    hit = None
    for op in ops:
        if op.type == capstone.arm.ARM_OP_MEM:
            b = ins.reg_name(op.mem.base)
            if b in regs and which(regs[b]) is not None and 0x40000000 <= regs[b] < 0x50000000:
                pb = which(regs[b]); off = op.mem.disp
                if 0 <= off < 0x400:
                    fam = NAME[pb][:3] if NAME[pb][:3] in ('TIM','GPIO','ADC') else ('I2C' if NAME[pb].startswith('I2C') else None)
                    rn = REGOFF.get(fam,{}).get(off,'+0x%X'%off) if fam else '+0x%X'%off
                    acc[pb][rn] += 1
                    hit = '%s.%s' % (NAME[pb], rn)
    ins_all.append((a,m,ins.op_str,None,hit))
    try:
        _, wr = ins.regs_access()
        for w in wr:
            rn = ins.reg_name(w)
            if rn in regs and regs[rn] < 0x40000000: del regs[rn]
    except Exception: pass

print('\n=== Pass2: 运行时外设访问（含经结构体的）===')
for pb, offs in sorted(acc.items(), key=lambda kv: -sum(kv[1].values())):
    print('  %-7s 0x%08X 共 %3d 次: %s' % (NAME.get(pb,'?'), pb, sum(offs.values()),
          ' '.join('%s(%d)' % (o,c) for o,c in offs.most_common(10))))

# 定时器寄存器访问点，按函数分组
TIMREGS = {'CR1','EGR','CCER','CCMR1','CCMR2','ARR','CCR1','CCR2','BDTR','PSC','DIER','RCR'}
func = None
func_hits = collections.defaultdict(set)
for (a,m,o,_,hit) in ins_all:
    if a in bl or func is None: func = a
    if hit and hit.split('.')[-1] in TIMREGS: func_hits[func].add(hit)
callers = collections.defaultdict(list)
for (a,m,o,_,hit) in ins_all:
    if m.startswith('bl') and '#' in o:
        try: callers[int(o.strip().lstrip('#'),16)].append(a)
        except Exception: pass
print('\n=== 访问定时器寄存器的函数（候选震动/驱动控制）===')
for f, hits in sorted(func_hits.items(), key=lambda kv: -len(kv[1]))[:12]:
    print('  函数 0x%08X : %s' % (f, ' '.join(sorted(hits)[:8])))
    print('        调用者 %d: %s' % (len(callers.get(f,[])), ' '.join('0x%X'%c for c in callers.get(f,[])[:8])))
