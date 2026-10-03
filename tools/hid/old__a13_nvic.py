import re
ASM = r"<WORKSPACE>"
LINE=re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
prog=[]
for ln,raw in enumerate(open(ASM,encoding='utf-8',errors='replace'),1):
    m=LINE.match(raw.strip())
    if m: prog.append((ln,int(m.group(1),16),m.group(2).strip(),m.group(3).strip()))
print("### function around NVIC code 0x0800FEE0..0x0800FF90")
for ln,a,mn,ops in prog:
    if 0x0800FEE0<=a<=0x0800FF90: print(f"   {a:08X}  {mn:8s} {ops}")
print()
print("### all callers of 0x0800FF00..0x0800FF50 entries (find the NVIC-enable entry point)")
for ln,a,mn,ops in prog:
    if mn in ('bl','blx') and ops.startswith('#'):
        t=int(ops.lstrip('#'),16)
        if 0x0800FEE0<=t<=0x0800FF60: print(f"   called from {a:08X} line{ln}: {mn} {ops}")
print()
print("### call sites passing small irq numbers: search 'movs r0, #0x1f/#0x20' or '#0x1e/#0x1f' before a bl")
for i,(ln,a,mn,ops) in enumerate(prog):
    if mn in ('movs','mov.w','movw','mov') and re.search(r',\s*#(0x1e|0x1f|0x20|0x21)\b',ops):
        nxt = prog[i+1] if i+1<len(prog) else (0,0,'','')
        print(f"   {a:08X}  {mn:6s} {ops:22s} -> next {nxt[1]:08X} {nxt[2]} {nxt[3]}")
