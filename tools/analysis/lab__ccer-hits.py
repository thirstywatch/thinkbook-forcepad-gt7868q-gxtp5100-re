import re
ASM = r"<WORKSPACE>"
lines = open(ASM, encoding="utf-8", errors="ignore").read().splitlines()
pat = re.compile(r"^\s*([0-9a-f]{8})\s+(\S+)\s*(.*)$")
recs=[]
for i,l in enumerate(lines):
    m=pat.match(l)
    if m: recs.append((int(m.group(1),16), m.group(2), m.group(3).strip(), i))
print("=== 全部写 offset 0x20 的指令（CCER 候选）===")
n=0
for addr,mnem,ops,i in recs:
    if not mnem.startswith("str"): continue
    m=re.match(r"(r\d+),\s*\[(r\d+)(?:,\s*#(0x[0-9a-f]+))?\]", ops)
    if not m: continue
    off=int(m.group(3),16) if m.group(3) else 0
    if off!=0x20: continue
    n+=1
    # 向上找该基址寄存器的来源
    basereg=m.group(2)
    src=""
    for k in range(i-1, max(0,i-12), -1):
        if re.search(rf"movw\s+{basereg},\s*#0x", lines[k]) or re.search(rf"movt\s+{basereg},\s*#0x", lines[k]):
            src=lines[k].strip(); break
    print(f"  #{n:2d} 0x{addr:08X}  {mnem} {ops}")
    print(f"        基址来源线索: {src if src else '(前 12 行内未见 movw/movt，可能来自栈或结构体)'}")
print()
print(f"共 {n} 处")
