# fw_timers.py — 修正版：收集所有立即数操作数，定位每个定时器基址的引用点与随后的寄存器写入
import struct, collections, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
code = data[VOFF + 0x140:]
def foff(a): return VOFF + (a - BASE)

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True

TIMERS = {0x40000000:'TIM2', 0x40000400:'TIM3', 0x40000800:'TIM4', 0x40000C00:'TIM5',
          0x40001000:'TIM6', 0x40001400:'TIM7', 0x40012C00:'TIM1', 0x40013400:'TIM8'}
GPIO = {0x40010800:'GPIOA', 0x40010C00:'GPIOB', 0x40011000:'GPIOC', 0x40011400:'GPIOD', 0x40011800:'GPIOE'}

alls = []
for ins in md.disasm(code, BASE + 0x140):
    if ins.id == 0:
        continue
    try: ops = ins.operands
    except Exception: continue
    imms = []
    for op in ops:
        if op.type == capstone.arm.ARM_OP_IMM:
            imms.append(op.imm & 0xFFFFFFFF)
    alls.append((ins.address, ins.mnemonic, ins.op_str, imms))

print('指令数 %d' % len(alls))

# 1) 所有立即数里出现定时器/GPIO 基址的位置
print('\n=== 各外设基址作为立即数出现的位置 ===')
for base, nm in {**TIMERS, **GPIO}.items():
    hits = []
    for (a, m, os_, imms) in alls:
        for v in imms:
            if v == base:
                hits.append((a, m, os_))
    if hits:
        print('\n  %-6s 0x%08X  出现 %d 次:' % (nm, base, len(hits)))
        for (a, m, os_) in hits[:8]:
            print('      0x%08X  %-9s %s' % (a, m, os_))

# 2) 对出现次数最多的定时器，dump 引用点之后的 22 条指令（看寄存器写入）
def dump_after(addr, n=22):
    print('   ... 0x%08X 起的 %d 条:' % (addr, n))
    c = 0
    for ins in md.disasm(data[foff(addr):foff(addr)+n*4], addr):
        print('        0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))
        c += 1
        if c >= n: break

best = None
for base, nm in TIMERS.items():
    n = sum(1 for (a,m,o,i) in alls for v in i if v == base)
    if best is None or n > best[1]:
        best = (nm, n, base)
print('\n=== 引用最多的定时器: %s (0x%08X, %d 次) ===' % (best[0], best[2], best[1]))
for (a, m, os_, imms) in alls:
    if best[2] in imms:
        print('\n--- 引用点 0x%08X: %s %s ---' % (a, m, os_))
        dump_after(a, 22)
