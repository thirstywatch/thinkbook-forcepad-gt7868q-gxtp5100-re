import re, struct, sys, collections
ASM = r"<WORKSPACE>"
LINE = re.compile(r'^([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)$')
lines = []
for ln, raw in enumerate(open(ASM, encoding='utf-8', errors='replace'), 1):
    s = raw.rstrip('\n')
    m = LINE.match(s.strip())
    if m:
        lines.append((ln, int(m.group(1),16), m.group(2).strip(), m.group(3).strip()))
    else:
        lines.append((ln, None, None, s))
print("total asm lines", len(lines), "parsed", sum(1 for l in lines if l[1] is not None))
addrs = [l[1] for l in lines if l[1] is not None]
print("addr range", hex(min(addrs)), hex(max(addrs)))
# contiguity check
gaps = [(lines[i][1], lines[i+1][1]) for i in range(len(lines)-1)
        if lines[i][1] is not None and lines[i+1][1] is not None and lines[i+1][1]-lines[i][1] not in (2,4)]
print("non-contiguous transitions (addr gaps / 2-byte-instr jumps):", len(gaps))
for g in gaps[:10]: print("   ", hex(g[0]), "->", hex(g[1]))

# does the listing cover 0x08005000-0x08012C9F contiguously?
print("first addr", hex(addrs[0]), "last addr", hex(addrs[-1]))
# which addresses are 4-byte instr (32-bit)? compare with capstone later.

# ---- constant materialization scan: movw Rd,#imm + optional movt Rd,#imm ----
def imm(ops):
    m = re.search(r'#(-?0x[0-9a-fA-F]+|-?\d+)', ops)
    return int(m.group(1), 16) if m and m.group(1).lower().startswith(('0x','-0x')) else (int(m.group(1)) if m else None)
def reg(ops):
    m = re.match(r'\s*(r\d+|sp|lr|pc|sl|fp|ip)\s*,', ops)
    return m.group(1) if m else None
def loads(ops):
    return re.findall(r'\[([^\]]*)\]', ops)

consts = []   # (lineno, addr, regname, value, method)
for i,(ln,a,mn,ops) in enumerate(lines):
    if a is None or mn is None: continue
    if mn == 'movw':
        r = reg(ops); v = imm(ops)
        if r is None or v is None: continue
        val = v & 0xFFFF; how = 'movw'
        # look ahead for movt on same reg before it is overwritten or >12 instrs
        for j in range(i+1, min(i+14, len(lines))):
            ln2,a2,mn2,ops2 = lines[j]
            if a2 is None or mn2 is None: continue
            # stop if any instruction writes to r
            dst_ok = False
            if mn2 in ('movt',):
                r2 = reg(ops2); v2 = imm(ops2)
                if r2 == r and v2 is not None:
                    val = ((v2 & 0xFFFF) << 16) | (v & 0xFFFF); how='movw+movt'
                    break
            # detect writes to r (destination is first operand for most)
            if re.match(r'\s*'+re.escape(r)+r'\s*,', ops2) or re.match(r'\s*'+re.escape(r)+r'\s*$', ops2) or mn2 in ('ldr','ldrb','ldrh','ldrsb','ldrsh') and reg(ops2)==r:
                # ldr Rd,[..] writes Rd
                if mn2.startswith('ldr') and reg(ops2)==r: break
                if mn2 in ('mov','movs','add','adds','sub','subs','add.w','sub.w','and','orr','eor','mvn','adr','movw','movt','uxtb','sxtb','uxth','sxth','ubfx','sbfx') and reg(ops2)==r: break
                if mn2 in ('pop','ldm','ldmia') : pass
        consts.append((ln, a, r, val, how))

print()
print("=== ALL 32-bit constants materialized via movw(/movt) that fall in 0x40000000-0x4001FFFF or 0xE0000000-0xE0100000 ===")
hit=0
for ln,a,r,val,how in consts:
    if (0x40000000 <= val < 0x40020000) or (0xE0000000 <= val < 0xE0100000):
        print(f"  line{ln:6d} {a:08X}  {r:4s} = {val:#010x}   ({how})")
        hit+=1
print("hits:", hit)
