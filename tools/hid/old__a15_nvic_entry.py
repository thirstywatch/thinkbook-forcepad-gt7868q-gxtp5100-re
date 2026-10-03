import re
ASM = r"<WORKSPACE>"
LINE=re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
prog=[]
for ln,raw in enumerate(open(ASM,encoding='utf-8',errors='replace'),1):
    m=LINE.match(raw.strip())
    if m: prog.append((ln,int(m.group(1),16),m.group(2).strip(),m.group(3).strip()))
print("### 0x0800FDC0-0x0800FE70")
for ln,a,mn,ops in prog:
    if 0x0800FDC0<=a<=0x0800FE70: print(f"   {a:08X}  {mn:8s} {ops}")
print()
# entry = last push before 0x0800FE62
cands=[(a,mn,ops) for ln,a,mn,ops in prog if 0x0800FD00<=a<=0x0800FE62 and mn=='push']
print("push candidates:",[(hex(c[0]),c[2]) for c in cands])
entry=cands[-1][0]
print("assumed ENTRY:",hex(entry))
V={}
print()
print("### callers of the NVIC helper (entry) with tracked r0/r1")
for i,(ln,a,mn,ops) in enumerate(prog):
    if mn in ('movs','mov','mov.w','movw'):
        m=re.match(r'(r\d+)\s*,\s*#(0x[0-9a-fA-F]+|\d+)',ops)
        if m: V[m.group(1)]=int(m.group(2),16) if m.group(2).lower().startswith('0x') else int(m.group(2))
        continue
    if mn in ('bl','blx') and ops.startswith('#'):
        t=int(ops.lstrip('#'),16)
        if t==entry:
            print(f"   {a:08X} line{ln}: r0={V.get('r0')} r1={V.get('r1')} r2={V.get('r2')} r3={V.get('r3')}")
        for r in ('r0','r1','r2','r3'): V.pop(r,None)
        continue
    m=re.match(r'\s*(r\d+)\s*[,!]',ops)
    if m and mn not in ('cmp','tst','str','strb','strh','push','b','beq','bne','bhi','bls','bx','cbz','cbnz','it','ands','orrs','ands.w'):
        V.pop(m.group(1),None)
