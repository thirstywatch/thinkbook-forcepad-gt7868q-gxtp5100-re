import re, struct, sys
ASM = r"<WORKSPACE>"
BIN = r"<WORKSPACE>"
BASE_ADDR = 0x08005000; BASE_OFF = 0x19ABC
blob = open(BIN,'rb').read()
def rd32(a):
    o = a - BASE_ADDR + BASE_OFF
    if 0 <= o <= len(blob)-4: return struct.unpack_from('<I', blob, o)[0]
    return None

LINE = re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
prog = []
for ln, raw in enumerate(open(ASM, encoding='utf-8', errors='replace'), 1):
    m = LINE.match(raw.strip())
    if m: prog.append((ln, int(m.group(1),16), m.group(2).strip(), m.group(3).strip()))

def num(s):
    s = s.strip()
    m = re.match(r'^#?(0x[0-9a-fA-F]+|\d+)$', s)
    return int(m.group(1), 16 if m.group(1).lower().startswith('0x') else 10) if m else None

REG = re.compile(r'^(r\d+|sp|lr|pc|ip|sl|fp|sb)$')
def parse(ops):
    # returns (dst, srcs, memexpr)
    o = ops.strip()
    mem = re.findall(r'\[([^\]]+)\]', o)
    noMem = re.sub(r'\[[^\]]+\]', '', o)
    parts = [p.strip() for p in noMem.split(',') if p.strip()]
    return parts, mem

# ---- collect branch targets to reset state ----
targets = set()
for ln,a,mn,ops in prog:
    for t in re.findall(r'#(0x[0-9a-fA-F]+)', ops):
        v = int(t,16)
        if 0x08005000 <= v <= 0x08012C9F and mn.startswith(('b','cb')):
            targets.add(v)
        if v & 1: pass
    if mn in ('ldr','ldrb','ldrh','ldr.w') and 'pc' in ops:
        pass
print("branch targets collected:", len(targets))

HELPERS = {0x800fc20:'SETBIT(base,desc)', 0x800fc80:'TESTFLAG(base,desc)', 0x800fc44:'CLRFLAG(base,desc)',
           0x800fc0c:'OR1(base)', 0x800f9cc:'ACK(base,en)', 0x800f9f8:'POS(base,en)',
           0x800fd24:'OAR_WRITE(base,cr1,hi,addr)', 0x800fa20:'CLOCKINIT(base,speed,duty)',
           0x800fbf8:'WRITEREG8(base,val)', 0x800f81c:'GPIO_CFG(port,pin,mode,af)',
           0x800fe3c:'PIN_CFG?', 0x80101d8:'GETCLK?'}
I2C_LO, I2C_HI = 0x40005400, 0x40005500

def run(clear_at_targets=True, clear_after_call=True):
    V = {}
    out = []
    for (ln,a,mn,ops) in prog:
        if clear_at_targets and a in targets and a != prog[0][1]:
            V = {}
        try:
            if mn == 'movw':
                m = re.match(r'(r\d+|ip|sl|fp|sb)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)', ops)
                if m:
                    r = m.group(1); v = num(m.group(2))
                    lo = V.get(r, (0,0))[0]
                    V[r] = (v, 0xFFFF)
                    out.append(('CONST', ln, a, r, v, 'movw'))
                continue
            if mn == 'movt':
                m = re.match(r'(r\d+|ip|sl|fp|sb)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)', ops)
                if m:
                    r = m.group(1); hi = num(m.group(2))
                    if r in V:
                        lo, lm = V[r]
                        V[r] = ((lo & 0xFFFF) | ((hi & 0xFFFF) << 16), 0xFFFFFFFF)
                    continue
            if mn in ('mov','movs','mov.w'):
                m = re.match(r'(r\d+|ip|sl|fp|sb)\s*,\s*(#0x[0-9a-fA-F]+|#\d+|r\d+|ip|sl|fp|sb)', ops)
                if m:
                    d = m.group(1); s = m.group(2)
                    if s in V: V[d] = V[s]
                    elif num(s) is not None: V[d] = (num(s), 0xFFFF if num(s) <= 0xFFFF else 0xFFFFFFFF)
                    else: V.pop(d, None)
                continue
            if mn in ('add','adds','add.w','sub','subs','sub.w'):
                m = re.match(r'(r\d+)\s*,\s*(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)', ops)
                if m:
                    d, s, i = m.group(1), m.group(2), num(m.group(3))
                    if s == d and s not in V:
                        pass
                    if s in V:
                        v = V[s][0] + (i if mn.startswith('add') else -i)
                        V[d] = (v & 0xFFFFFFFF, V[s][1])
                    else: V.pop(d, None)
                    continue
                m = re.match(r'(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)', ops)
                if m:
                    d, i = m.group(1), num(m.group(2))
                    if d in V:
                        v = V[d][0] + (i if mn.startswith('add') else -i)
                        V[d] = (v & 0xFFFFFFFF, V[d][1])
                    continue
                # add rX, rY  (register)
                m = re.match(r'(r\d+)\s*,\s*(r\d+)$', ops)
                if m:
                    d,s = m.group(1), m.group(2)
                    if d in V and s in V: V[d] = ((V[d][0]+V[s][0]) & 0xFFFFFFFF, V[d][1] & V[s][1])
                    else: V.pop(d, None)
                    continue
                d = reg0(ops)
                if d: V.pop(d, None)
                continue
            if mn in ('ldr','ldr.w','ldrb','ldrb.w','ldrh','ldrh.w','ldrsb','ldrsh'):
                parts, mem = parse(ops)
                if len(parts) >= 2:
                    d = parts[0]
                    if 'pc' in ops:
                        m = re.search(r'pc,\s*#(0x[0-9a-fA-F]+|\d+)', ops)
                        if m:
                            lit = ((a + 4) & ~3) + num('#'+m.group(1))
                            w = rd32(lit)
                            if w is not None: V[d] = (w, 0xFFFFFFFF)
                            else: V.pop(d, None)
                        else: V.pop(d, None)
                    else:
                        V.pop(d, None)
                continue
            if mn in ('ldr','ldrb','ldrh') and len(parse(ops)[0])==1:
                V.pop(parse(ops)[0][0], None); continue
            if mn in ('str','str.w','strb','strb.w','strh','strh.w'):
                parts, mem = parse(ops)
                if mem:
                    src = parts[0] if parts else None
                    expr = mem[0]
                    # base [+ #off]
                    m = re.match(r'^(r\d+|ip|sl|fp|sb)\s*(?:,\s*#(0x[0-9a-fA-F]+|\d+))?$', expr)
                    if m:
                        b = m.group(1); off = num('#'+m.group(2)) if m.group(2) else 0
                        if b in V:
                            tgt = (V[b][0] + off) & 0xFFFFFFFF
                            val = V.get(src, (None,0))[0] if src else None
                            out.append(('WRITE', ln, a, tgt, mn, src, val, 'base_reg=%s+%#x'%(b,off)))
                        else:
                            out.append(('WRITE_UNK', ln, a, None, mn, src, None, 'base=%s+%#x'%(b,off)))
                continue
            if mn in ('bl','blx') and ops.startswith('#'):
                t = num(ops.lstrip('#'))
                if t in HELPERS:
                    snap = {r:V.get(r,(None,0))[0] for r in ('r0','r1','r2','r3') if r in V}
                    out.append(('CALL', ln, a, t, HELPERS[t], snap, None, None))
                if clear_after_call:
                    for r in ('r0','r1','r2','r3','ip'): V.pop(r, None)
                continue
            # generic: kill destination register
            if mn in ('pop','ldm','ldmia','push','stm','stmia'):
                for t in re.findall(r'\b(r\d+|ip|sl|fp|sb|lr|pc)\b', ops):
                    V.pop(t, None)
                continue
            if mn.startswith('blx') or mn.startswith('bx') or mn.startswith('b') and not mn.startswith('bic') and not mn.startswith('bfc'):
                # branches don't clobber (except blx handled)
                if mn in ('blx',): 
                    for r in ('r0','r1','r2','r3','ip'): V.pop(r, None)
                continue
            d = reg0(ops)
            if d: V.pop(d, None)
        except Exception as e:
            pass
    return out

def reg0(ops):
    m = re.match(r'\s*(r\d+|ip|sl|fp|sb)\s*[,!]', ops)
    return m.group(1) if m else None

res = run(clear_at_targets=False, clear_after_call=True)
res2 = run(clear_at_targets=True, clear_after_call=False)

def dump(res, tag):
    print("="*100)
    print("### MODE:", tag)
    print("-- (A) CALLs to hardware helpers with a KNOWN r0 in the I2C block --")
    for e in res:
        if e[0]=='CALL':
            snap = e[5] or {}
            r0 = snap.get('r0')
            if r0 is not None and I2C_LO <= r0 < I2C_HI:
                print(f"  line{e[1]:6d} {e[2]:08X}  {e[4]:26s} r0={r0:#010x} r1={snap.get('r1')} r2={snap.get('r2')} r3={snap.get('r3')}")
    print("-- (B) direct STOREs with known target inside I2C block --")
    for e in res:
        if e[0]=='WRITE' and e[3] is not None and I2C_LO <= e[3] < I2C_HI:
            print(f"  line{e[1]:6d} {e[2]:08X}  {e[4]:8s} [{e[3]:#010x}] <- {e[5]} = {e[6] if e[6] is None else hex(e[6])}   ({e[7]})")
    print("-- (C) direct LOADs with known target inside I2C block --")
for r,t in ((res,'no-reset'),(res2,'reset-at-targets')):
    dump(r,t)
print("="*100)
print("### ALL CALLs to the descriptor helpers anywhere (with arg snapshot), both modes union ###")
seen=set()
for res_,tag in ((res,'A'),(res2,'B')):
    for e in res_:
        if e[0]=='CALL':
            key=(e[2],e[4],tuple(sorted((e[5] or {}).items())))
            if key in seen: continue
            seen.add(key)
            print(f"  {tag} line{e[1]:6d} {e[2]:08X}  {e[4]:26s} {e[5]}")
