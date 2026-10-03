# find_lra2.py - 搜索 movw 低半字 = 设备结构体偏移，dump 上下文找出外设寄存器访问
import struct, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True
def foff(a): return VOFF + (a - BASE)

LOWS = {0x40B8:'struct TIM2 (0x200040B8)', 0x40BC:'TIM2字段+4', 0x40C0:'+8', 0x40C4:'+12',
        0x40C8:'+16', 0x40CC:'+20'}

# 收集所有 movw 低半字命中的位置
sites = []
for ins in md.disasm(data[VOFF+0x140:], BASE+0x140):
    if ins.id == 0: continue
    if ins.mnemonic == 'movw':
        try: ops = ins.operands
        except Exception: continue
        if len(ops) >= 2 and ops[1].type == capstone.arm.ARM_OP_IMM:
            v = ops[1].imm & 0xFFFF
            if v in LOWS:
                # 看下一条是否 movt 0x2000
                sites.append((ins.address, v, ins.reg_name(ops[0].reg)))

print('movw 命中 %d 处' % len(sites))
by_addr = {}
for a, v, r in sites:
    by_addr.setdefault(v, []).append((a, r))

for v, lst in sorted(by_addr.items()):
    print('\n=== %s  命中 %d 处 ===' % (LOWS[v], len(lst)))
    for a, r in lst[:6]:
        print('  引用点 0x%08X (reg %s)，上下文:' % (a, r))
        lo = a - 8
        cnt = 0
        for ins in md.disasm(data[foff(lo):foff(lo)+0x60], lo):
            if ins.id == 0:
                print('        0x%08X  <data>' % ins.address); continue
            print('        0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))
            cnt += 1
            if cnt >= 20: break
