# fw_callgraph.py — 建立调用图，从 PWM 配置点向上回溯高层上下文
import struct, collections, capstone

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
    tgt = None
    if ins.mnemonic.startswith('bl'):
        for op in ops:
            if op.type == capstone.arm.ARM_OP_IMM: tgt = op.imm
    alls.append((ins.address, ins.mnemonic, ins.op_str, tgt))

# 函数入口集合：所有 bl 目标 + 向量表入口
entries = set(t for (_,_,_,t) in alls if t)
for v in [0x08005164,0x0800A678,0x08008894,0x0800A448,0x080053F4,0x0800DFE4,0x0800BE24,0x0800B75C,0x0800CE7C,0x08006B3C,0x0800D628,0x08008978,0x0800894C,0x0800DEE8]:
    entries.add(v)
entries = sorted(entries)

def func_of(addr):
    lo, hi = 0, len(entries)-1
    best = entries[0]
    for e in entries:
        if e <= addr: best = e
        else: break
    return best

callers = collections.defaultdict(list)
for (a,m,o,t) in alls:
    if t: callers[t].append(a)

def show(name, addr, depth=0, seen=None):
    if seen is None: seen = set()
    f = func_of(addr)
    pad = '  ' * depth
    print('%s[%s] 函数 0x%08X (来自 0x%08X)' % (pad, name, f, addr))
    if f in seen or depth >= 4: return
    seen.add(f)
    cs = [c for c in callers.get(f, [])]
    if not cs:
        print('%s  └─ 无调用者' % pad)
    for c in cs[:6]:
        show('caller', c, depth+1, seen)

print('=== 从 PWM 配置点回溯 ===')
for site in (0x08008750, 0x08008766, 0x08008772, 0x0800877C, 0x0800903E):
    print('\n--- 配置点 0x%08X ---' % site)
    show('site', site, 1, set())

print('\n\n=== 出现 0x2BC / 0x7CF(1999) / 0x60 / 0x77 立即数的位置（另一套 PWM 参数）===')
for val in (0x2BC, 0x7CF, 0x60, 0x77):
    hits = [(a,m,o) for (a,m,o,t) in alls if ('#%d' % val) in o or ('#0x%x' % val) in o]
    print('  %d: %d 处 %s' % (val, len(hits), ' '.join('0x%X' % h[0] for h in hits[:10])))
