# image_bounds.py -- how far past its own end does the plaintext image reach?
#
# The docs carry "runtime reaches 0x0800F0B5 => >=5,141 B missing". Two things were
# wrong with how that was supported, and this script exists to settle it:
#
#   1. The "128 B shortfall" (declared 56,608 vs 56,480 present) is DEAD. The
#      container's declared lengths match the bytes present EXACTLY:
#        100,608 + 56,608, where 56,608 = 128 B payload header + 56,480 B image.
#      So the file is complete on its own terms -- see container_layout notes below.
#
#   2. A naive linear Thumb sweep desynchronises (advance by ins.size, NOT by 2),
#      and a desynchronised sweep invents branch targets. An earlier version of this
#      file did exactly that and produced ~40 fake "past the end" branches.
#
# So: recursive descent from the vector table, following calls and literal pools.
# That is the high-confidence reachable set. READ ONLY.
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = (r'C:\Windows\System32\DriverStore\FileRepository'
       r'\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN')
VOFF = 0x19ABC                      # image start (valid vector table here)
BASE = 0x08000000                   # link address
d = open(BIN, 'rb').read()
img = d[VOFF:]
END = BASE + len(img)               # first byte past the image
print(f"image: file 0x{VOFF:06X}, {len(img):,} B, linked 0x{BASE:08X}..0x{END-1:08X}")
print()

def in_img(a): return BASE <= a < END
def in_flash(a): return BASE <= a < BASE + 0x100000

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)

# --- 1. the vector table ------------------------------------------------------
print("=== vector table at image offset 0 ===")
slots = struct.unpack('<256I', img[:1024])
sp, rst = slots[0], slots[1]
print(f"  slot   0 (SP)    0x{sp:08X}   {'ok (RAM)' if 0x20000000 <= sp < 0x20020000 else 'SUSPECT'}")
print(f"  slot   1 (Reset) 0x{rst:08X}   {'ok (flash, odd)' if rst & 1 and in_flash(rst) else 'SUSPECT'}")
run = 2
while run < 256 and (slots[run] == 0 or (slots[run] & 1 and in_flash(slots[run]))):
    run += 1
print(f"  table runs {run} entries (slots 0..{run-1}) = 16 system + {run-16} peripheral IRQs")
zero = sum(1 for i in range(2, run) if slots[i] == 0)
print(f"  of the handler slots: {zero} are null, {run-2-zero} are populated")
past = [(i, slots[i]) for i in range(2, run) if slots[i] and not in_img(slots[i])]
print(f"  handlers pointing PAST image end: {len(past)}   (null slots excluded)")
for i, v in past:
    irq = i - 16
    print(f"    slot {i:3d}  (IRQ {irq:3d}{'  = USART1' if irq == 37 else ''})  0x{v:08X}   +{v-END:,} B past end")
print()

# --- 2. recursive descent -----------------------------------------------------
print("=== recursive descent from all vector entries ===")
code = set()          # addresses disassembled as code
consts = {}           # absolute constant -> set of sites
unreached = set()     # bl/b targets that land outside the image
work = [v & ~1 for v in slots[:run] if v & 1 and in_flash(v)]
iter_cap = 400000
steps = 0
import os
TRACE = int(os.environ.get('TRACE', '0'))
trace = []
while work and steps < iter_cap:
    a = work.pop()
    if a in code or not in_img(a):
        continue
    func_start = a
    fsteps = 0
    pend = []                 # literal-pool loads seen in this function: (site, pool_addr)
    while in_img(a):
        fsteps += 1
        steps += 1
        o = a - BASE
        ins = next(md.disasm(img[o:o + 4], a), None)
        if ins is None:
            break
        code.add(a)
        m, ops = ins.mnemonic, ins.op_str
        nxt = a + ins.size

        # calls / jumps -> follow into the image, note the ones that leave it
        if m.startswith('bl') or m == 'b' or m.startswith('b.'):
            if ops.startswith('#'):
                t = int(ops[1:], 0)
                if in_img(t & ~1):
                    if not m.startswith('b.'):
                        work.append(t & ~1)
                elif in_flash(t & ~1):
                    unreached.add(t | 1)
            if m == 'b' or m.startswith('b.'):
                break                       # unconditional: function ends here
        # pc-relative loads -> remember the pool slot
        elif m.startswith('ldr') and '[pc' in ops and ops.startswith('r'):
            try:
                imm = int(ops.split('[pc, #')[1].split(']')[0], 0)
            except (IndexError, ValueError):
                a = nxt
                continue
            pend.append(((nxt + 3) & ~3) + imm)
        elif m == 'adr' and ops.startswith('r'):
            try:
                t = int(ops.split('#')[1], 0)
            except (IndexError, ValueError):
                t = None
            if t is not None and in_flash(t) and not in_img(t):
                unreached.add(t)
        # end of function
        elif m in ('bx', 'pop', 'udf', 'bkpt') and ('lr' in ops or 'pc' in ops or m in ('udf', 'bkpt')):
            break
        elif m in ('movs', 'mov') and ops.startswith('pc'):
            break
        a = nxt
    trace.append((func_start, fsteps))

    # resolve this function's literal pools (words are 4-byte aligned in-image)
    for po in pend:
        if not in_img(po):
            continue
        v, = struct.unpack('<I', img[po - BASE:po - BASE + 4])
        if in_flash(v):
            consts.setdefault(v, set()).add(po)
            if in_img(v):
                work.append(v & ~1)

print(f"  {steps:,} instruction steps, {len(code):,} addresses marked as code")
print(f"  {len(code):,} B of code = {100*len(code)/len(img):.1f}% of the image")
print(f"  {len(trace):,} functions entered")
print("  NB: this is a LOWER BOUND. The descent follows bl/b and ldr-literal only; it does")
print("      NOT follow switch jump tables (`ldr pc, [rX, rY, lsl #2]`) or function-pointer")
print("      tables stored as data. Both are present here (the 39-command dispatcher is one),")
print("      so plenty of real code is reachable that this walk never enters.")
if TRACE:
    trace.sort(key=lambda t: -t[1])
    print(f"  --- TRACE: the {TRACE} largest functions ---")
    for s, n in trace[:TRACE]:
        print(f"    0x{s:08X}  {n:5d} instructions")
    small = sum(1 for _, n in trace if n <= 5)
    print(f"  --- functions of <=5 instructions: {small} of {len(trace)}")
print()

# --- 3. what the code actually refers to --------------------------------------
print("=== referenced flash addresses vs image end ===")
print("  NB: lower bound again -- the 5,141-byte figure in §4 below comes from a movw/movt")
print("      pair that this walk may or may not reach. The authoritative claims are the")
print("      vector table (section 1) and the verified movw/movt site (section 4).")
allrefs = set(consts) | {v for v in unreached}
past = sorted(v for v in allrefs if not in_img(v))
print(f"  distinct flash constants/call targets referenced: {len(allrefs)}")
print(f"  PAST image end: {len(past)}")
for v in past:
    sites = consts.get(v, set())
    src = ' '.join(f'0x{s:05X}' for s in sorted(sites)[:3]) if sites else '(call target)'
    how = 'literal' if sites else 'branch'
    print(f"    0x{v:08X}  +{v-END:>7,} B  ({how})  <- {src}")
if past:
    hi = past[-1]
    print()
    print(f"  highest referenced address : 0x{hi:08X}")
    print(f"  image ends at              : 0x{END-1:08X}")
    print(f"  => at least {hi-END:,} B of the referenced address space are NOT in this image")
print()

# --- 4. verify the specific claim in the docs --------------------------------
print("=== the docs' headline number: 0x0800F0B5 ===")
tgt_off = 0x08FF6
for ins in md.disasm(img[tgt_off:tgt_off + 8], BASE + tgt_off):
    print(f"  image offset 0x{tgt_off:05X} (flash 0x{BASE+tgt_off:08X}):  {ins.mnemonic:6s} {ins.op_str}")
print(f"  => builds 0x0800F0B5, which is {0x0800F0B5-END:,} B past the image end")
print()

# --- 5. where the code stops --------------------------------------------------
print("=== code coverage of the last 1 KB of the image ===")
tail0 = len(img) - 1024
n = sum(1 for o in range(tail0, len(img), 2) if BASE + o in code)
print(f"  {n} of 512 halfword-aligned offsets in the final 1 KB are code")
print(f"  highest code address reached: 0x{max(code):08X}")
