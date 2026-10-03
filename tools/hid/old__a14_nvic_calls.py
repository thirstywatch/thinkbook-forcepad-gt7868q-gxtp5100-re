import re
ASM = r"<WORKSPACE>"
LINE=re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
prog=[]
for ln,raw in enumerate(open(ASM,encoding='utf-8',errors='replace'),1):
    m=LINE.match(raw.strip())
    if m: prog.append((ln,int(m.group(1),16),m.group(2).strip(),m.group(3).strip()))
print("### find NVIC-enable function entry (search backwards from 0x0800FF00 for push)")
idx=[i for i,(ln,a,mn,ops) in enumerate(prog) if a==0x0800FF00][0]
for j in range(idx, idx-60, -1):
    ln,a,mn,ops=prog[j]
    if mn=='push':
        print(f"   probable ENTRY {a:08X}  {mn} {ops}"); entry=a; break
print("   -- prologue --")
for ln,a,mn,ops in prog:
    if entry<=a<=0x0800FF00: print(f"     {a:08X}  {mn:8s} {ops}")

# simple tracker to get r0 at each call to that entry
V={}
print()
print("### ALL call sites of the NVIC enable function with tracked r0 (IRQ number)")
for i,(ln,a,mn,ops) in enumerate(prog):
    if mn=='movs' or mn=='mov' or mn=='mov.w':
        m=re.match(r'(r\d+)\s*,\s*#(0x[0-9a-fA-F]+|\d+)',ops)
        if m: V[m.group(1)]=int(m.group(2),16) if m.group(2).lower().startswith('0x') else int(m.group(2))
        continue
    if mn=='movw':
        m=re.match(r'(r\d+)\s*,\s*#(0x[0-9a-fA-F]+|\d+)',ops)
        if m: V[m.group(1)]=int(m.group(2),16) if m.group(2).lower().startswith('0x') else int(m.group(2))
        continue
    if mn in ('bl','blx') and ops.startswith('#'):
        t=int(ops.lstrip('#'),16)
        if t==entry:
            print(f"   {a:08X} line{ln}: irq r0={V.get('r0')}  prio r1={V.get('r1')}")
        V.pop('r0',None); V.pop('r1',None); V.pop('r2',None); V.pop('r3',None)
        continue
    m=re.match(r'\s*(r\d+)\s*[,!]',ops)
    if m and mn not in ('cmp','tst','str','strb','strh','push','b','beq','bne','bhi','bls','bx','cbz','cbnz','it','ands','orrs'):
        V.pop(m.group(1),None)
