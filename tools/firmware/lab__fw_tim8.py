# fw_tim8.py — 反汇编 TIM8 配置函数，并回溯调用者（判断是马达驱动还是传感器驱动）
import struct, collections, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
code = data[VOFF + 0x140:]
def foff(a): return VOFF + (a - BASE)

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True

def dis(tag, addr, n=60):
    print('\n=== %s @0x%08X ===' % (tag, addr))
    c = 0
    for ins in md.disasm(data[foff(addr):foff(addr)+n*4], addr):
        print('  0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))
        c += 1
        if c >= n: break

dis('TIM8 配置(0x0800BBF0 附近)', 0x0800BBC0, 70)
dis('PWM 通道配置(0x0800B5AC 附近)', 0x0800B580, 55)

# 找出所有调用 [0x0800B560, 0x0800BC40] 区间的 bl，打印调用点前后各 6 条指令作为上下文
LO, HI = 0x0800B560, 0x0800BC40
alls = []
for ins in md.disasm(code, BASE + 0x140):
    if ins.id == 0: continue
    alls.append((ins.address, ins.mnemonic, ins.op_str))

print('\n\n=== 调用 TIM8 相关函数的调用点（带上下文）===')
n = 0
for i, (a, m, os_) in enumerate(alls):
    if m.startswith('bl') and '#' in os_:
        try: t = int(os_.strip().lstrip('#'), 16)
        except Exception: continue
        if LO <= t <= HI:
            n += 1
            print('\n--- 调用点 0x%08X -> 0x%08X ---' % (a, t))
            for j in range(max(0, i-7), min(len(alls), i+4)):
                mark = '>>' if j == i else '  '
                print('  %s 0x%08X  %-9s %s' % (mark, alls[j][0], alls[j][1], alls[j][2]))
            if n >= 8: break
print('\n共找到 %d 个调用点（最多显示 8 个）' % n)
