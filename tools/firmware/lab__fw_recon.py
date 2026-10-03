# fw_recon.py — 触控板固件初步侦察：定位向量表、确认加载地址、反汇编复位处理
import struct, sys
import capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
n = len(data)
def u32(off):
    return struct.unpack_from('<I', data, off)[0]

print('文件大小: %d 字节' % n)

# ---- 1. 找候选向量表：SP 在 SRAM 区，随后是奇数(Thumb)的 Flash 地址 ----
cands = []
for i in range(0, n - 4*40, 4):
    sp = u32(i); rv = u32(i+4)
    if 0x20000000 <= sp < 0x20080000 and (rv & 1) and 0x08000000 <= rv < 0x08100000:
        cnt = 0
        for k in range(2, 40):
            v = u32(i + 4*k)
            if v == 0 or ((v & 1) and 0x08000000 <= v < 0x08100000):
                cnt += 1
        if cnt >= 30:
            cands.append((i, sp, rv, cnt))

print('\n=== 候选向量表 ===')
for (off, sp, rv, cnt) in cands:
    print('  file_off=0x%X (%d)  SP=0x%08X  Reset=0x%08X  有效项=%d' % (off, off, sp, rv, cnt))

if not cands:
    print('未找到向量表，尝试放宽条件...')
    for i in range(0, n - 4*40, 4):
        sp = u32(i); rv = u32(i+4)
        if 0x20000000 <= sp < 0x20100000 and (rv & 1) and 0x08000000 <= rv < 0x08200000:
            cands.append((i, sp, rv, 0))
    for c in cands[:10]:
        print('  file_off=0x%X SP=0x%08X Reset=0x%08X' % (c[0], c[1], c[2]))

if not cands:
    sys.exit(0)

VOFF, SP0, RESET, _ = cands[0]
BASE = 0x08000000
def foff(addr):
    return VOFF + (addr - BASE)

print('\n镜像映射假设: file_off 0x%X <-> 0x%08X' % (VOFF, BASE))
print('SRAM 顶(初始 MSP)=0x%08X  -> SRAM 大小约 %d KB' % (SP0, (SP0 - 0x20000000)//1024))
print('复位向量=0x%08X -> file_off 0x%X' % (RESET, foff(RESET & ~1)))

# ---- 2. 打印前 16 个向量 ----
print('\n=== 向量表前 16 项 ===')
names = ['SP', 'Reset', 'NMI', 'HardFault', 'MemManage', 'BusFault', 'UsageFault', 'Resv', 'Resv', 'Resv', 'Resv', 'SVC', 'DebugMon', 'Resv', 'PendSV', 'SysTick']
for k in range(16):
    v = u32(VOFF + 4*k)
    print('  %-10s 0x%08X' % (names[k], v))

# ---- 3. 反汇编复位处理函数 ----
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = False
start = foff(RESET & ~1)
code = data[start:start + 400]
print('\n=== 反汇编 @0x%08X (file 0x%X) 复位处理 ===' % (RESET & ~1, start))
for ins in md.disasm(code, RESET & ~1):
    print('  0x%08X  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
    if ins.mnemonic in ('bx', 'pop') and 'pc' in ins.op_str:
        break
