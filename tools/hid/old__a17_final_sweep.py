import struct, collections
BIN = r"<WORKSPACE>"
BASE_ADDR=0x08005000; BASE_OFF=0x19ABC; SEG=56480
blob=open(BIN,'rb').read(); seg=blob[BASE_OFF:BASE_OFF+SEG]

def dec(hw0,hw1):
    """return (kind,Rd,imm16) for movw (kind='w') / movt (kind='t') else None"""
    if (hw0 & 0xFBF0)==0xF240: kind='w'
    elif (hw0 & 0xFBF0)==0xF2C0: kind='t'
    else: return None
    i=(hw0>>10)&1; imm4=hw0&0xF
    imm3=(hw1>>12)&0x7; Rd=(hw1>>8)&0xF; imm8=hw1&0xFF
    return (kind,Rd,(imm4<<12)|(i<<11)|(imm3<<8)|imm8)

print("sanity: known movw sites")
for a in (0x0800894E,0x08008A98,0x08008B58,0x080064F4,0x08010AB6,0x080110D4):
    o=a-BASE_ADDR; h0,h1=struct.unpack_from('<HH',seg,o)
    print(f"  {a:08X}  hw=({h0:#06x},{h1:#06x}) -> {dec(h0,h1)}")

# resolve movw(+movt same reg within 6 halfwords, no intervening write to that reg apparent)
res=collections.defaultdict(list)
nw=nt=0
for o in range(0,SEG-3,2):
    h0,h1=struct.unpack_from('<HH',seg,o)
    d=dec(h0,h1)
    if not d: continue
    kind,Rd,imm=d
    if kind=='t': nt+=1; continue
    nw+=1
    a=BASE_ADDR+o; val=imm; full=False
    for k in range(2,14,2):
        if o+k+3>=SEG: break
        g0,g1=struct.unpack_from('<HH',seg,o+k)
        t=dec(g0,g1)
        if t and t[0]=='t' and t[1]==Rd:
            val=(t[2]<<16)|imm; full=True; break
    res[(a,Rd,imm,full,val)].append(1)

print()
print("=== ALL movw sites whose resolved value is a peripheral address (0x40000000-0x4001FFFF) or 0xE00xxxxx ===")
rows=[k for k in res if (0x40000000<=k[4]<0x40020000) or (0xE0000000<=k[4]<0xE0100000)]
for a,Rd,imm,full,val in sorted(rows):
    print(f"  {a:08X}  r{Rd:2d}  imm16={imm:#06x}  {'+movt' if full else 'MOVW-ONLY(!)'}  = {val:#010x}")
print("  count:", len(rows))

print()
print("=== every movw site with imm16 == 0x5400 / 0x5410 / 0x5414 / 0x5800 (whole segment) ===")
for a,Rd,imm,full,val in sorted(res):
    if imm in (0x5400,0x5410,0x5414,0x5800):
        print(f"  {a:08X} r{Rd:2d} imm16={imm:#06x} {'+movt -> '+hex(val) if full else '(movt NOT adjacent)'}")
print()
print("total movw decoded:",nw," total movt decoded:",nt)
print("does any resolved peripheral constant equal 0x40005400/0x40005800 ?",
      [hex(k[4]) for k in res if k[4] in (0x40005400,0x40005800)])
print("listing tail not covered by the .asm.txt (0x08012342-0x08012C9F) contains an I2C constant? NO"
      if not any(0x08012342<=k[0]<=0x08012C9F and 0x40005400<=k[4]<0x40005C00 for k in res) else "YES")
