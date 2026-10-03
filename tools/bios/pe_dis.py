"""从 FFS 文件里抽出 PE32 段并用 capstone 线性扫描反汇编。"""
import struct, sys, io

SEC_TYPES={0x01:"COMPRESSION",0x02:"GUID_DEFINED",0x03:"DISPOSABLE",0x10:"PE32",0x11:"PIC",
 0x12:"TE",0x13:"DXE_DEPEX",0x14:"VERSION",0x15:"UI",0x16:"COMPAT16",0x17:"FV_IMAGE",
 0x18:"FREEFORM_GUID",0x19:"RAW",0x1B:"PEI_DEPEX",0x1C:"SMM_DEPEX"}

def walk_sections(d, off, end):
    """返回 [(section_type, body_bytes, off)]"""
    out=[]; guard=0
    while off+4<=end and guard<5000:
        guard+=1
        size=d[off]|(d[off+1]<<8)|(d[off+2]<<16); st=d[off+3]
        if size==0xFFFFFF:
            gd=d[off+4:off+20]; doff,attr=struct.unpack_from("<HH",d,off+20)
            realsize=struct.unpack_from("<I",d,off+20)[0]
            if realsize<24 or off+realsize>end: return out
            out.append((st, d[off+doff:off+realsize], off))
            off=(off+realsize+3)&~3; continue
        if size<4 or off+size>end: return out
        out.append((st, d[off+4:off+size], off))
        off=(off+size+3)&~3
    return out

def ffs_body(path):
    d=open(path,"rb").read()
    fsz=d[20]|(d[21]<<8)|(d[22]<<16)
    return d, walk_sections(d, 24, fsz if 24<=fsz<=len(d) else len(d))

def pick_pe(secs):
    for st,body,off in secs:
        if st in (0x10,0x12,0x11) and len(body)>0x40:
            return st, body, off
    # 有些 RAW 段里直接是 PE
    for st,body,off in secs:
        if body[:2]==b"MZ": return 0x99, body, off
    return None,None,None

def pe_info(pe):
    if pe[:2]!=b"MZ": return None
    e=struct.unpack_from("<I",pe,0x3C)[0]
    if pe[e:e+4]!=b"PE\0\0": return None
    machine,nsec=struct.unpack_from("<HH",pe,e+4)
    sizeso=struct.unpack_from("<H",pe,e+0x14)[0]
    oh=e+24
    magic=struct.unpack_from("<H",pe,oh)[0]
    ep=struct.unpack_from("<I",pe,oh+16)[0]
    base=struct.unpack_from("<Q",pe,oh+24)[0] if magic==0x20B else struct.unpack_from("<I",pe,oh+28)[0]
    st=oh+sizeso
    secs=[]
    for i in range(nsec):
        o=st+i*40
        name=pe[o:o+8].rstrip(b"\0").decode("latin1")
        vsz,va,rsz,pra=struct.unpack_from("<IIII",pe,o+8)
        ch=struct.unpack_from("<I",pe,o+36)[0]
        secs.append((name,va,vsz,pra,rsz,ch))
    return dict(machine=machine,ep=ep,base=base,secs=secs,magic=magic)

def linear_sweep(code, addr, md, max_skip_ratio=0.25):
    """线性扫描，遇到无法解码就前进 1 字节重开（capstone 遇坏字节会静默停止）"""
    import capstone
    insns=[]; off=0; bad=0
    while off < len(code):
        got=list(md.disasm(code[off:], addr+off))
        if got:
            insns.extend(got)
            off += sum(i.size for i in got)
        else:
            off += 1; bad += 1
    return insns, bad

def disasm_pe(path, verbose=False):
    d,secs=ffs_body(path)
    st,pe,off=pick_pe(secs)
    if not pe: return None
    info=pe_info(pe)
    if not info: return None
    import capstone
    mode = capstone.CS_MODE_64 if info["magic"]==0x20B else capstone.CS_MODE_32
    md=capstone.Cs(capstone.CS_ARCH_X86, mode)
    md.detail=True
    allinsn=[]
    EXEC  = 0x20000000   # IMAGE_SCN_MEM_EXECUTE
    CODE  = 0x00000020   # IMAGE_SCN_CNT_CODE
    for name,va,vsz,pra,rsz,ch in info["secs"]:
        if not (ch & (EXEC | CODE)):     # 只看可执行/代码段
            continue
        code=pe[pra:pra+rsz]
        if not code: continue
        insns,bad=linear_sweep(code, info["base"]+va, md)
        allinsn.append((name, info["base"]+va, code, insns, bad))
    return dict(secs=secs, pe=pe, info=info, insn_groups=allinsn)

if __name__=="__main__":
    r=disasm_pe(sys.argv[1])
    if not r: print("不是 PE"); sys.exit(1)
    print("machine=0x%X magic=0x%X entry=0x%X base=0x%X"%(r["info"]["machine"],r["info"]["magic"],
          r["info"]["ep"],r["info"]["base"]))
    print("FFS 段:"+", ".join("%s(0x%X)"%(SEC_TYPES.get(s[0],hex(s[0])),len(s[1])) for s in r["secs"]))
    tot=0
    for name,addr,code,insns,bad in r["insn_groups"]:
        print("  %-8s @0x%X size=0x%-6X 指令=%d 坏字节=%d"%(name,addr,len(code),len(insns),bad))
        tot+=len(insns)
    print("总指令 = %d"%tot)
