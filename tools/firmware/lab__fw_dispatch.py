# fw_dispatch.py — 1) 多编码假设搜索报告描述符  2) 扫描 jump table / 报文 ID 比较（定位 HID 分派器）
import struct, collections, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
code = data[VOFF + 0x140:]

def find(pat, label):
    res = []
    i = data.find(pat)
    while i >= 0:
        res.append(i)
        i = data.find(pat, i + 1)
    print('  %-42s 命中 %d 处 %s' % (label, len(res), res[:5]))
    return res

print('=== 1) 报告描述符多编码假设 ===')
ptp = bytes.fromhex('050D0905A101')          # UsagePage(Digitizers) Usage(TouchPad) Collection(App)
find(ptp, 'PTP 集合 明文')
find(b''.join(bytes([c, 0]) for c in ptp), 'PTP 集合 每字节后补 00')
find(ptp[::-1], 'PTP 集合 逆序')
find(bytes([0x06, 0x00, 0xFF, 0x09, 0x01, 0xA1, 0x01]), '厂商集合 06 00 FF 09 01 A1 01')
find(bytes.fromhex('050E0901'), 'Haptics 05 0E 09 01')

print('\n=== 2) 反汇编扫描：jump table 与报文 ID 比较 ===')
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True

tb_sites = []
cmp_sites = collections.defaultdict(list)
n = 0
for ins in md.disasm(code, BASE + 0x140):
    n += 1
    if ins.id == 0:
        continue
    try:
        ops = ins.operands
    except Exception:
        continue
    if ins.mnemonic in ('tbb', 'tbh'):
        tb_sites.append('0x%08X  %s %s' % (ins.address, ins.mnemonic, ins.op_str))
    if ins.mnemonic in ('cmp', 'cmp.w') and len(ops) == 2 and ops[1].type == capstone.arm.ARM_OP_IMM:
        imm = ops[1].imm
        if imm in (2, 4, 6, 9, 11, 12, 13, 14, 15):
            cmp_sites[imm].append(ins.address)

print('反汇编 %d 条指令' % n)
print('\n-- tbb/tbh（switch 跳转表，分派器常用）: %d 处 --' % len(tb_sites))
for s in tb_sites[:25]:
    print('   ' + s)

print('\n-- 与报文 ID 立即数比较的位置（按立即数分组，只列前 12 个地址）--')
for imm in sorted(cmp_sites):
    addrs = cmp_sites[imm]
    print('  cmp #%-3d 共 %3d 处: %s' % (imm, len(addrs), ' '.join('0x%X' % a for a in addrs[:12])))
