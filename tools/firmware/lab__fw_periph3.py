# fw_periph3.py — 修正版：解析常量池 PC 相对载入 + 外设映射 + 函数调用关系
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

PERIPH = {}
for b, nm in [(0x40010000,'AFIO'),(0x40010400,'EXTI'),(0x40010800,'GPIOA'),(0x40010C00,'GPIOB'),
              (0x40011000,'GPIOC'),(0x40011400,'GPIOD'),(0x40011800,'GPIOE'),(0x40011C00,'GPIOF'),
              (0x40012000,'ADC1'),(0x40012400,'ADC1reg'),(0x40000000,'TIM2'),(0x40000400,'TIM3'),
              (0x40000800,'TIM4'),(0x40000C00,'TIM5'),(0x40001000,'TIM6'),(0x40001400,'TIM7'),
              (0x40012C00,'TIM1'),(0x40013400,'TIM8'),(0x40005400,'I2C1'),(0x40005800,'I2C2'),
              (0x40003800,'SPI2'),(0x40013000,'SPI1'),(0x40004400,'USART2'),(0x40004800,'USART3'),
              (0x40004C00,'UART4'),(0x40005000,'UART5'),(0x40021000,'RCC'),(0x40022000,'FLASH'),
              (0x40007000,'PWR'),(0x40006C00,'BKP'),(0x40020000,'DMA1'),(0x40020400,'DMA2'),
              (0x40005C00,'USB'),(0x40006000,'CAN'),(0x40006C00,'BKP')]:
    PERIPH[b] = nm

def which(a):
    best = None
    for pb in PERIPH:
        if pb <= a < pb + 0x400 and (best is None or pb > best):
            best = pb
    return best

regs = {}
acc = collections.defaultdict(collections.Counter)
instrs = []          # (addr, mnemonic, op_str, periph_or_None, offset)
bl_targets = set()

for ins in md.disasm(code, CSTART):
    if ins.id == 0:
        continue
    try:
        ops = ins.operands
    except Exception:
        continue
    m = ins.mnemonic
    a = ins.address

    if m in ('movw', 'movt') and len(ops) >= 2 and ops[0].type == capstone.arm.ARM_OP_REG and ops[1].type == capstone.arm.ARM_OP_IMM:
        r = ins.reg_name(ops[0].reg); v = ops[1].imm & 0xFFFF
        regs[r] = v if m == 'movw' else ((regs.get(r, 0) & 0xFFFF) | (v << 16))
        instrs.append((a, m, ins.op_str, None, 0)); continue

    # 常量池 PC 相对载入
    if m in ('ldr', 'ldr.w') and len(ops) == 2 and ops[0].type == capstone.arm.ARM_OP_REG and ops[1].type == capstone.arm.ARM_OP_MEM \
       and ins.reg_name(ops[1].mem.base) == 'pc':
        lit = ((a + 4) & 0xFFFFFFFC) + ops[1].mem.disp
        v = rd32(lit)
        if v is not None:
            regs[ins.reg_name(ops[0].reg)] = v
        instrs.append((a, m, ins.op_str, None, 0)); continue

    if m.startswith('bl'):
        for op in ops:
            if op.type == capstone.arm.ARM_OP_IMM:
                bl_targets.add(op.imm)

    hit = None
    for op in ops:
        if op.type == capstone.arm.ARM_OP_MEM:
            b = ins.reg_name(op.mem.base)
            if b in regs:
                addr = (regs[b] + op.mem.disp) & 0xFFFFFFFF
                pb = which(addr)
                if pb is not None:
                    acc[pb][addr - pb] += 1
                    hit = (pb, addr - pb)
    instrs.append((a, m, ins.op_str, hit[0] if hit else None, hit[1] if hit else 0))

    try:
        _, written = ins.regs_access()
        for w in written:
            rn = ins.reg_name(w)
            if rn in regs:
                del regs[rn]
    except Exception:
        pass

print('指令数 %d，bl 目标（近似函数入口）%d 个' % (len(instrs), len(bl_targets)))
print('\n=== 外设映射（修正后）===')
for pb, offs in sorted(acc.items(), key=lambda kv: -sum(kv[1].values())):
    print('  %-10s 0x%08X 共 %3d 次   偏移: %s' % (PERIPH[pb], pb, sum(offs.values()),
          ' '.join('+0x%X(%d)' % (o, c) for o, c in offs.most_common(10))))

# 找出访问了「非 I2C/RCC/FLASH/PWR/BKP」外设的函数，并列出调用者
INTERESTING = [pb for pb, nm in PERIPH.items() if nm.startswith(('TIM', 'GPIO', 'SPI', 'ADC'))]
func_hits = collections.defaultdict(set)
cur = None
for (a, m, os_, pb, off) in instrs:
    if a in bl_targets or cur is None:
        cur = a
    if pb in INTERESTING:
        func_hits[cur].add((PERIPH[pb], off))

callers = collections.defaultdict(list)
for (a, m, os_, pb, off) in instrs:
    if m.startswith('bl') and '#' in os_:
        try:
            t = int(os_.strip().lstrip('#'), 16)
        except Exception:
            continue
        callers[t].append(a)

print('\n=== 访问 TIM/GPIO/SPI/ADC 的函数（候选马达/传感器驱动）===')
for f, hits in sorted(func_hits.items(), key=lambda kv: -len(kv[1]))[:15]:
    cl = callers.get(f, [])
    desc = ' '.join('%s+0x%X' % h for h in sorted(hits)[:8])
    print('  函数 0x%08X : %s' % (f, desc))
    print('        被调用 %d 次，来自: %s' % (len(cl), ' '.join('0x%X' % c for c in cl[:10])))
