# fw_rda.py - recursive-descent disassembler for the touchpad firmware
# seeds: vector table + function pointers found in init code; follows branches; never sweeps data
import struct, collections, capstone, sys

BIN = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
data = open(BIN, 'rb').read()
VOFF, BASE = 0x19ABC, 0x08000000
IMG_END = BASE + (len(data) - VOFF)
def foff(a): return VOFF + (a - BASE)
def u32(a): return struct.unpack_from('<I', data, foff(a))[0]

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.detail = True

TERM = {'bx','b','pop','blx'}   # note: 'b' handled specially (conditional vs unconditional)

insns = {}          # addr -> (mnemonic, op_str)
visited = set()
work = []

# seeds
for i in range(76):
    v = u32(BASE + 4*i)
    if v and (v & 1) and BASE <= (v & ~1) < IMG_END:
        work.append(v & ~1)
# callbacks found in init code + previously discovered entries
for a in (0x0800DB38, 0x0800DB5C, 0x0800DADC, 0x0800D628, 0x0800DEE8, 0x08008978, 0x0800894C,
          0x08005164, 0x08006B3C, 0x0800CE7C, 0x0800B75C, 0x0800BE24):
    work.append(a)

while work:
    start = work.pop()
    if start in visited or not (BASE <= start < IMG_END - 3):
        continue
    off = foff(start)
    # disassemble a run starting here (cap length to avoid runaway)
    n = 0
    for ins in md.disasm(data[off:off+4000], start):
        a = ins.address
        if a in visited:
            break
        if ins.id == 0:      # hit data -> stop this run
            break
        visited.add(a)
        insns[a] = (ins.mnemonic, ins.op_str)
        n += 1
        m = ins.mnemonic
        # follow direct branches
        for op in ins.operands:
            if op.type == capstone.arm.ARM_OP_IMM and m in ('b','bl','blx','cbz','cbnz') or \
               (op.type == capstone.arm.ARM_OP_IMM and m.startswith('b') and m not in ('bic','bfc','bfi')):
                t = op.imm
                if BASE <= t < IMG_END:
                    work.append(t & ~1)
        if m in ('bx',) or (m == 'pop' and 'pc' in ins.op_str) or (m == 'b' and n > 0 and not ins.op_str.startswith('#')):
            break
        if m == 'b' and ins.op_str.startswith('#'):
            break            # unconditional branch: run ends
        if n > 900:
            break

print('recursive-descent disassembly: %d instructions decoded' % len(insns))
addrs = sorted(insns)
print('range: 0x%08X .. 0x%08X' % (addrs[0], addrs[-1]) if addrs else 'none')

# how much of the tail region got decoded?
tail = [a for a in addrs if a >= 0x0800D000]
print('instructions in tail region (>=0x0800D000): %d' % len(tail))

def dump(a, n=45):
    print('\n=== code @0x%08X ===' % a)
    cur = a
    for _ in range(n):
        if cur not in insns: 
            print('   ... (no code at 0x%08X)' % cur); break
        m, o = insns[cur]
        print('  0x%08X  %-9s %s' % (cur, m, o))
        cur += 4 if _is32(cur) else 2
        while cur not in insns and cur < a + n*4:
            cur += 2

def _is32(addr):
    return False

# simpler dump: iterate sorted addresses within a window
def window(a, size=0x120):
    print('\n=== window 0x%08X..0x%08X ===' % (a, a+size))
    for x in addrs:
        if a <= x < a+size:
            m, o = insns[x]
            print('  0x%08X  %-9s %s' % (x, m, o))

window(0x0800DB38, 0x90)
window(0x0800DADC, 0x60)
window(0x0800DEE8, 0x60)

# save decoded listing for later analysis
with open(r'<LAB>\touchpad-lab\re\decoded.txt', 'w', encoding='utf-8') as f:
    for a in addrs:
        m, o = insns[a]
        f.write('0x%08X\t%s\t%s\n' % (a, m, o))
print('\nsaved listing to decoded.txt')
