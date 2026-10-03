import re
ASM = r"<WORKSPACE>"
LINE=re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
prog=[]
for ln,raw in enumerate(open(ASM,encoding='utf-8',errors='replace'),1):
    m=LINE.match(raw.strip())
    if m: prog.append((ln,int(m.group(1),16),m.group(2).strip(),m.group(3).strip()))
def num(s):
    m=re.match(r'^#?(0x[0-9a-fA-F]+|\d+)$',s.strip())
    return int(m.group(1),16 if m.group(1).lower().startswith('0x') else 10) if m else None
I2C_LO,I2C_HI=0x40005400,0x40005500

V={}
hits=[]
for ln,a,mn,ops in prog:
    if mn=='movw':
        m=re.match(r'(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)',ops)
        if m: V[m.group(1)]=num(m.group(2))
        continue
    if mn=='movt':
        m=re.match(r'(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)',ops)
        if m and m.group(1) in V: V[m.group(1)]=((V[m.group(1)]&0xFFFF)|((num(m.group(2))&0xFFFF)<<16))
        continue
    if mn in ('mov','movs','mov.w'):
        m=re.match(r'(r\d+)\s*,\s*(#?0x[0-9a-fA-F]+|#?\d+|r\d+)',ops)
        if m:
            d,s=m.group(1),m.group(2)
            if s in V: V[d]=V[s]
            elif num(s) is not None: V[d]=num(s)
            else: V.pop(d,None)
        continue
    if mn in ('add','adds','add.w','sub','subs'):
        m=re.match(r'(r\d+)\s*,\s*(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)',ops)
        if m:
            d,s,i=m.group(1),m.group(2),num(m.group(3))
            if s in V: V[d]=(V[s]+(i if mn.startswith('add') else -i))&0xFFFFFFFF
            else: V.pop(d,None)
            continue
        m=re.match(r'(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)',ops)
        if m and m.group(1) in V: V[m.group(1)]=(V[m.group(1)]+(num(m.group(2)) if mn.startswith('add') else -num(m.group(2))))&0xFFFFFFFF
        continue
    # memory operand: report if ANY register inside [] is tracked in the I2C range
    mems=re.findall(r'\[([^\]]+)\]',ops)
    for mem in mems:
        regs=re.findall(r'\b(r\d+|ip|sl|fp|sb|sp|pc)\b',mem)
        for r in regs:
            if r in V and I2C_LO<=V[r]<I2C_HI:
                hits.append((ln,a,mn,ops,r,hex(V[r])))
    if mn in ('bl','blx') and ops.startswith('#'):
        for r in ('r0','r1','r2','r3','ip'): V.pop(r,None)
        continue
    if mn.startswith('ldr'):
        m=re.match(r'(r\d+)\s*,',ops)
        if m: V.pop(m.group(1),None)
        continue
    if mn in ('pop','ldm','ldmia'):
        for t in re.findall(r'\b(r\d+|ip|sl|fp|sb)\b',ops): V.pop(t,None)
        continue
    m=re.match(r'\s*(r\d+|ip|sl|fp|sb)\s*[,!]',ops)
    if m and mn not in ('cmp','tst','str','strb','strh','str.w','strb.w','strh.w','push','b','beq','bne','bhi','bls','bcs','bcc','bx','blx','cbz','cbnz','it','ands','orrs','bics','uxtb','uxth','sxtb','sxth','ubfx','sbfx','lsls','lsrs','asrs'):
        V.pop(m.group(1),None)

print("### EVERY memory access (load OR store, any addressing form) whose base register is tracked to 0x400054xx")
for ln,a,mn,ops,r,v in hits:
    print(f"  line{ln:6d} {a:08X}  {mn:8s} {ops:34s}  [{r}={v}]")
print("  total:", len(hits))
