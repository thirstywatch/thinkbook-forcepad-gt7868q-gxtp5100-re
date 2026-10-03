# fw_debug.py - 1) debug operand types 2) check second cmp #14 site 3) disasm I2C-adjacent region
import struct, capstone

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
def foff(a): return VOFF + (a - BASE)

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True
md.skipdata = True

print('=== 1) operand debug: 0x08009026..0x0800903E ===')
for ins in md.disasm(data[foff(0x08009026):foff(0x08009026)+0x18], 0x08009026):
    d = []
    for op in ins.operands:
        t = op.type
        if t == capstone.arm.ARM_OP_REG: d.append('REG(%s)' % ins.reg_name(op.reg))
        elif t == capstone.arm.ARM_OP_IMM: d.append('IMM(0x%X)' % op.imm)
        elif t == capstone.arm.ARM_OP_MEM: d.append('MEM(base=%s,disp=0x%X)' % (ins.reg_name(op.mem.base), op.mem.disp))
        else: d.append('T%d' % t)
    print('  0x%08X  %-9s %-30s -> %s' % (ins.address, ins.mnemonic, ins.op_str, ' '.join(d)))

print('\n=== 2) second cmp #14 site: 0x0800DB90 ===')
for ins in md.disasm(data[foff(0x0800DB90):foff(0x0800DB90)+0x60], 0x0800DB90):
    tag = '   <-- DATA BYTE (not instruction)' if ins.id == 0 else ''
    print('  0x%08X  %-9s %s%s' % (ins.address, ins.mnemonic, ins.op_str, tag))

print('\n=== 3) I2C-adjacent region 0x08008A46 (suspected HID command handling) ===')
for ins in md.disasm(data[foff(0x08008A46):foff(0x08008A46)+0x100], 0x08008A46):
    print('  0x%08X  %-9s %s' % (ins.address, ins.mnemonic, ins.op_str))
