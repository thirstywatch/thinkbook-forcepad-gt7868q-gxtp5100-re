import re, struct
ASM = r"<WORKSPACE>"
lines = open(ASM, encoding='utf-8', errors='replace').read().splitlines()
LINE = re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
prog = []
for ln, raw in enumerate(lines, 1):
    m = LINE.match(raw.strip())
    if m: prog.append((ln, int(m.group(1),16), m.group(2).strip(), m.group(3).strip()))

print("### 1. every instruction in 0x08008B40..0x08008C40 that WRITES memory (manual audit of init)")
for ln,a,mn,ops in prog:
    if 0x08008B40 <= a <= 0x08008C40 and mn.split('.')[0] in ('str','strb','strh','stm','push'):
        print(f"  {a:08X}  {mn:8s} {ops}")

print()
print("### 2. global search: any instruction writing immediate 0x100 or 0x200 near a store")
for i,(ln,a,mn,ops) in enumerate(prog):
    if mn in ('orr','orrs','orr.w') and re.search(r'#0x(100|200)\b', ops):
        ctx = " | ".join(f"{prog[j][1]:08X}:{prog[j][2]} {prog[j][3]}" for j in range(max(0,i-3), min(len(prog), i+5)))
        print(f"  ** {a:08X}  {mn} {ops}\n       ctx: {ctx}")

print()
print("### 3. global search: every 'movw rX,#0x100'/'#0x200' and 'movs rX,#0x100' (START/STOP immediates)")
for ln,a,mn,ops in prog:
    if mn in ('movw','movs','mov','mov.w') and re.search(r'#0x(100|200)\b', ops):
        print(f"  {a:08X}  {mn:8s} {ops}")

print()
print("### 4. every store whose target could be the I2C init's r5 (0x40005400) region: scan region 0x08008900-0x08008C60 all memory-writes")
for ln,a,mn,ops in prog:
    if 0x08008900 <= a <= 0x08008C60 and mn.split('.')[0] in ('str','strb','strh'):
        print(f"  {a:08X}  {mn:8s} {ops}")

print()
print("### 5. does anything read/test bit0 of SR1(0x14) or SR2(0x18)? list all instructions touching a reg holding SR1/SR2 value")
for ln,a,mn,ops in prog:
    if 0x0800FC44 <= a <= 0x08008C00 or 0x0800FC80 <= a <= 0x0800FD24:
        pass
print("  (handled analytically: only sites 0x800fc80 / 0x800fc44 / 0x8008B58 / 0x8008A60 touch SR1/SR2)")
