import re
ASM = r"<WORKSPACE>"
BIN = r"<WORKSPACE>"
BASE_ADDR=0x08005000; BASE_OFF=0x19ABC
import struct
blob=open(BIN,'rb').read()
def rd32(a):
    o=a-BASE_ADDR+BASE_OFF
    return struct.unpack_from('<I',blob,o)[0] if 0<=o<=len(blob)-4 else None
LINE=re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
prog=[]
for ln,raw in enumerate(open(ASM,encoding='utf-8',errors='replace'),1):
    m=LINE.match(raw.strip())
    if m: prog.append((ln,int(m.group(1),16),m.group(2).strip(),m.group(3).strip()))
def num(s):
    m=re.match(r'^#?(0x[0-9a-fA-F]+|\d+)$',s.strip())
    return int(m.group(1),16 if m.group(1).lower().startswith('0x') else 10) if m else None
I2C_LO,I2C_HI=0x40005400,0x40005500

# --- global: track r0..r3 and report EVERY bl whose r0 is in the I2C block ---
V={}
rows=[]
for ln,a,mn,ops in prog:
    if mn=='movw':
        m=re.match(r'(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)',ops)
        if m: V[m.group(1)]=(num(m.group(2)),0xFFFF)
        continue
    if mn=='movt':
        m=re.match(r'(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)',ops)
        if m and m.group(1) in V:
            lo,_=V[m.group(1)]; V[m.group(1)]=((lo&0xFFFF)|((num(m.group(2))&0xFFFF)<<16),0xFFFFFFFF)
        continue
    if mn in ('mov','movs','mov.w'):
        m=re.match(r'(r\d+)\s*,\s*(#?0x[0-9a-fA-F]+|#?\d+|r\d+)',ops)
        if m:
            d,s=m.group(1),m.group(2)
            if s in V: V[d]=V[s]
            elif num(s) is not None: V[d]=(num(s),0xFFFF)
            else: V.pop(d,None)
        continue
    if mn in ('add','adds','add.w','sub','subs'):
        m=re.match(r'(r\d+)\s*,\s*(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)',ops)
        if m:
            d,s,i=m.group(1),m.group(2),num(m.group(3))
            if s in V: V[d]=((V[s][0]+(i if mn.startswith('add') else -i))&0xFFFFFFFF,V[s][1])
            else: V.pop(d,None)
            continue
        m=re.match(r'(r\d+)\s*,\s*(#0x[0-9a-fA-F]+|#\d+)',ops)
        if m and m.group(1) in V:
            V[m.group(1)]=(V[m.group(1)][0]+(num(m.group(2)) if mn.startswith('add') else -num(m.group(2))),V[m.group(1)][1])
        continue
    if mn in ('bl','blx') and ops.startswith('#'):
        t=num(ops.lstrip('#'))
        r0=V.get('r0',(None,0))[0]
        if r0 is not None and I2C_LO<=r0<I2C_HI:
            rows.append((ln,a,t,r0,V.get('r1',(None,0))[0],V.get('r2',(None,0))[0],V.get('r3',(None,0))[0]))
        for r in ('r0','r1','r2','r3','ip'): V.pop(r,None)
        continue
    if mn in ('ldr','ldrb','ldrh','ldr.w','ldrb.w','ldrh.w') or mn.startswith('ldr'):
        m=re.match(r'(r\d+)\s*,',ops)
        if m: V.pop(m.group(1),None)
        continue
    if mn in ('pop','ldm','ldmia'):
        for t in re.findall(r'\b(r\d+|ip|sl|fp|sb)\b',ops): V.pop(t,None)
        continue
    m=re.match(r'\s*(r\d+|ip|sl|fp|sb)\s*[,!]',ops)
    if m and mn not in ('cmp','tst','str','strb','strh','push','b','beq','bne','bhi','bls','bcs','bcc','bx','blx','cbz','cbnz','it'):
        V.pop(m.group(1),None)

print("### EVERY `bl` in the whole image invoked with r0 == an address in 0x40005400-0x400054FF")
for ln,a,t,r0,r1,r2,r3 in rows:
    print(f"  line{ln:6d} {a:08X}  bl {t:#010x}   args r0={r0:#x} r1={r1 if r1 is None else hex(r1)} r2={r2 if r2 is None else hex(r2)} r3={r3 if r3 is None else hex(r3)}")
print("  total:", len(rows))

print()
print("### callers of 0x0800EF20 (the orr #0x100 / #0x400 on [base+4]) and of 0x0800EF20 region")
for ln,a,mn,ops in prog:
    if mn=='bl' and ops.startswith('#') and int(ops.lstrip('#'),16) in (0x800EF20,):
        print(f"  {a:08X} line{ln}: {mn} {ops}")
print("  -- function body 0x0800EF20-0x0800EFE0 --")
for ln,a,mn,ops in prog:
    if 0x0800EF20<=a<=0x0800EFE0: print(f"   {a:08X}  {mn:8s} {ops}")
