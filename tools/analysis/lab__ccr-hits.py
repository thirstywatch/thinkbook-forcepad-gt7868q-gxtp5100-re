import re
ASM = r"<WORKSPACE>"
lines = open(ASM, encoding="utf-8", errors="ignore").read().splitlines()
pat = re.compile(r"^\s*([0-9a-f]{8})\s+(\S+)\s*(.*)$")
recs=[]
for i,l in enumerate(lines):
    m=pat.match(l)
    if m: recs.append((int(m.group(1),16), m.group(2), m.group(3).strip(), i))
print("=== 全部写 offset 0x34/0x38/0x3C/0x40（CCR1..CCR4）的指令 ===")
for addr,mnem,ops,i in recs:
    if not mnem.startswith("str"): continue
    m=re.match(r"(r\d+),\s*\[(r\d+)(?:,\s*#(0x[0-9a-f]+))?\]", ops)
    if not m: continue
    off=int(m.group(3),16) if m.group(3) else 0
    if off in (0x34,0x38,0x3c,0x40):
        print("="*74)
        print(f"0x{addr:08X}  {mnem} {ops}   ← CCR 偏移 0x{off:02X}")
        for k in range(max(0,i-12), min(len(lines),i+5)):
            mark="  >>" if k==i else "    "
            print(f"{mark} {lines[k].rstrip()}")
print()
print("=== 反向：搜所有把 0x40000000(TIM2) / 0x40000400(TIM3) 基址载入寄存器的点，看其后 12 行内有无 CCR 写 ===")
for idx,(addr,mnem,ops,i) in enumerate(recs):
    if mnem in ("movw","mov") and "#0x0" in ops and idx+1<len(recs) and recs[idx+1][1]=="movt" and "#0x4000" in recs[idx+1][2]:
        reg=ops.split(",")[0].strip()
        base=0x40000000 | int(ops.split("#")[1],16)
        if base not in (0x40000000,0x40000400): continue
        print("="*74)
        print(f"  TIM 基址 0x{base:08X} 载入 {reg}  @0x{addr:08X}")
        for k in range(i, min(len(lines), i+16)):
            mark="  >>" if k==i else "    "
            print(f"{mark} {lines[k].rstrip()}")
