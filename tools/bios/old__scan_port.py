import sys
from pe_dis import disasm_pe
PORTS={0x60,0x61,0x62,0x63,0x64,0x65,0x66,0x67,0x68,0x6C,0x80,0x84,0x408,0x1804,0x1808,0x1800}
MMIO_HINT=(0xFE000000,0xFEE00000,0xFE0B0000)
def scan(path):
    r=disasm_pe(path); 
    if not r: return
    print("="*74); print("### %s"%path.split("/")[-1])
    hits=[]
    for name,base,code,insns,bad in r["insn_groups"]:
        for i,ins in enumerate(insns):
            for op in ins.operands:
                if op.type==2:
                    v=op.imm
                    if v in PORTS or (MMIO_HINT[0]<=v<=0xFFFFFFFF and (v>>16)!=0xFFFFFFFF and v>0xFE000000):
                        hits.append((ins.address,ins.mnemonic,ins.op_str,v,i,insns))
    print("命中 %d 处"%len(hits))
    seen=set()
    for a,m,o,v,i,insns in hits:
        key=(v,)
        if (v,m) in seen and len(seen)>40: continue
        seen.add((v,m))
        print("\n  >> 0x%06X  %-8s %-28s  [imm=0x%X]"%(a,m,o,v))
        for j in range(max(0,i-4),min(len(insns),i+5)):
            mk="   >>" if j==i else "     "
            print("%s %08X  %-8s %s"%(mk,insns[j].address,insns[j].mnemonic,insns[j].op_str))
    return r
for p in sys.argv[1:]: scan(p)
