import re
ASM = r"<WORKSPACE>"
LINE = re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
prog=[]
for ln,raw in enumerate(open(ASM,encoding='utf-8',errors='replace'),1):
    m=LINE.match(raw.strip())
    if m: prog.append((ln,int(m.group(1),16),m.group(2).strip(),m.group(3).strip()))

# function starts in the I2C driver region
print("### function boundaries in 0x08008800-0x08008D00 (push {..lr} / movs r0,r0 padding)")
region=[(a,mn,ops) for ln,a,mn,ops in prog if 0x08008800<=a<=0x08008D00]
for i,(a,mn,ops) in enumerate(region):
    if mn=='push' and ('lr' in ops):
        print(f"   ENTRY {a:08X}  {mn} {ops}")

print()
print("### every branch-with-link target anywhere in the image that lands in 0x08008800-0x08008D00")
callers={}
for ln,a,mn,ops in prog:
    if mn in ('bl','blx') and ops.startswith('#'):
        t=int(ops.lstrip('#'),16)
        if 0x08008800<=t<=0x08008D00:
            callers.setdefault(t,[]).append((a,ln))
for t in sorted(callers):
    print(f"   target {t:08X} called from {[hex(x[0]) for x in callers[t]]} (lines {[x[1] for x in callers[t]]})")

print()
print("### who calls 0x8008C34 and 0x800DA4C ?")
for tgt in (0x8008C34,0x800DA4C,0x800DA4C+0):
    hits=[(a,ln) for ln,a,mn,ops in prog if mn in ('bl','blx') and ops.startswith('#') and int(ops.lstrip('#'),16)==tgt]
    print(f"   0x{tgt:08X}: {[(hex(h[0]),h[1]) for h in hits]}")

print()
print("### 0x08010A00-0x08010AD0 : the 'peripheral base' sequence (TIM table?)")
for ln,a,mn,ops in prog:
    if 0x080109E0<=a<=0x08010AD0: print(f"   {a:08X}  {mn:8s} {ops}")

print()
print("### 0x0800EF20-0x0800EF60 (the orr #0x100 on [r1+4])")
for ln,a,mn,ops in prog:
    if 0x0800EF00<=a<=0x0800EF60: print(f"   {a:08X}  {mn:8s} {ops}")

print()
print("### 0x0800DA40-0x0800DA60 (function entry owning I2C init)")
for ln,a,mn,ops in prog:
    if 0x0800DA30<=a<=0x0800DA6E: print(f"   {a:08X}  {mn:8s} {ops}")
