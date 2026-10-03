import sys, struct, re
from pe_dis import disasm_pe, ffs_body, pick_pe, pe_info

def g(b):
    a,b2,c=struct.unpack_from("<IHH",b,0)
    return "%08X-%04X-%04X-%s-%s"%(a,b2,c,b[8:10].hex().upper(),b[10:16].hex().upper())

def dump(path, outtxt):
    r=disasm_pe(path)
    if not r: print("非 PE",path); return None
    lines=[]
    for name,base,code,insns,bad in r["insn_groups"]:
        for ins in insns:
            lines.append("%08X  %-8s %s"%(ins.address,ins.mnemonic,ins.op_str))
    open(outtxt,"w",encoding="utf-8").write("\n".join(lines))
    print("%-24s 指令 %d -> %s"%(path.split('/')[-1],len(lines),outtxt))

    # GUID 扫描（在 PE 所有非代码数据里找 16 字节 GUID 模式）
    pe=r["pe"]; info=r["info"]
    data=b"".join(pe[pra:pra+rsz] for name,va,vsz,pra,rsz,ch in info["secs"] if not (ch & (0x20000000|0x20)))
    guids=set()
    for i in range(0,len(data)-16):
        b=data[i:i+16]
        d1,d2,d3=struct.unpack_from("<IHH",b,0)
        # GUID 启发：Data3 版本号常见 0x1xxx-0x4xxx，Data4 第一个字节常见 0x8/0x9/0xA/0xB
        if 0x1000<=d3<=0x4FFF and b[8] in (0x80,0x81,0x82,0x83,0x84,0x85,0x86,0x87,0x88,0x89,0x8a,0x8b,0x8c,0x8d,0x8e,0x8f,0x90,0x91,0x92,0x93,0x94,0x95,0x96,0x97,0x98,0x99,0x9a,0x9b,0x9c,0x9d,0x9e,0x9f,0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xab,0xac,0xad,0xae,0xaf,0xb0,0xb1,0xb2,0xb3,0xb4,0xb5,0xb6,0xb7,0xb8,0xb9,0xba,0xbb,0xbc,0xbd,0xbe,0xbf):
            guids.add(g(b))
    print("   候选 GUID %d 个:"%len(guids))
    for x in sorted(guids): print("      ",x)
    return r

if __name__=="__main__":
    for p in sys.argv[1:]:
        r=dump(p, p.split('/')[-1].replace('.bin','.asm.txt'))
