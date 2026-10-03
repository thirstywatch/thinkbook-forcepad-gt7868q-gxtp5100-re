# fw_chain.py — 反汇编 I2C→PWM 调用链上的函数，判断是「开机初始化」还是「主机命令下发」
import struct, capstone, collections

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
code = data[VOFF + 0x140:]
def foff(a): return VOFF + (a - BASE)

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True

alls = []
for ins in md.disasm(code, BASE + 0x140):
    if ins.id == 0: continue
    try: ops = ins.operands
    except Exception: continue
    t = None
    if ins.mnemonic.startswith('bl'):
        for op in ops:
            if op.type == capstone.arm.ARM_OP_IMM: t = op.imm
    alls.append((ins.address, ins.mnemonic, ins.op_str, t))
callers = collections.defaultdict(list)
for (a,m,o,t) in alls:
    if t: callers[t].append(a)

def dis(tag, addr, n=48):
    print('\n=== %s @0x%08X ===' % (tag, addr))
    c = 0
    for ins in md.disasm(data[foff(addr):foff(addr)+n*4], addr):
        print('  0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))
        c += 1
        if c >= n: break
    # 该函数的调用者
    cs = callers.get(addr, [])
    if cs:
        print('  [调用者] %s' % ' '.join('0x%X' % c for c in cs[:10]))

dis('0x08008FE8 (PWM 配置执行者)', 0x08008FE8, 50)
dis('0x0800AD24 (中间层)', 0x0800AD24, 40)
dis('0x08003B68 (I2C 驱动区)', 0x08003B68, 40)
dis('0x08008A4C (I2C 中断邻近)', 0x08008A4C, 40)

print('\n=== 0x08008A4C 的调用者，以及它是否在中断路径里 ===')
print('0x08008A4C 调用者: %s' % ' '.join('0x%X' % c for c in callers.get(0x08008A4C, [])[:10]))
print('0x08008A4C 附近的函数入口候选: %s' % ' '.join('0x%X' % c for c in sorted(callers.get(0x08008A4C, []))[:1]))
