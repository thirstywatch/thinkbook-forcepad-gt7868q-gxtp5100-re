import struct, sys
FS2 = bytes.fromhex("78e58c8c3d8a1c4f9935896185c32dd3")
def g(b):
    d1,d2,d3 = struct.unpack_from("<IHH",b,0)
    return "%08X-%04X-%04X-%s-%s"%(d1,d2,d3,b[8:10].hex().upper(),b[10:16].hex().upper())
FFS_TYPES={0x01:"RAW",0x02:"FREEFORM",0x03:"SEC_CORE",0x04:"PEI_CORE",0x05:"DXE_CORE",
 0x06:"PEIM",0x07:"DXE_DRIVER",0x08:"COMBINED_PEIM",0x09:"APP",0x0A:"MM",0x0B:"FV_IMAGE",
 0x0C:"COMBINED_MM_DXE",0x0D:"MM_CORE",0x0E:"MM_STANDALONE",0x0F:"MM_CORE_STD",0xF0:"PAD"}
SEC={0x01:"COMPRESS",0x02:"GUID_DEF",0x03:"DISPOSABLE",0x10:"PE32",0x11:"PIC",0x12:"TE",
 0x13:"DXE_DEPEX",0x14:"VERSION",0x15:"UI",0x16:"COMPAT16",0x17:"FV_IMAGE",0x18:"FREEFORM_GUID",
 0x19:"RAW",0x1B:"PEI_DEPEX",0x1C:"SMM_DEPEX"}
LZMA_GUID = bytes.fromhex("9858ee4e14395942d69ede7bd79403cf")  # EE4E5898-3914-4259-9D6E-DC7BD79403CF

def walk_sections(d, off, end, depth, out, base):
    guard=0
    while off+4 <= end and guard<20000:
        guard+=1
        size = d[off]|(d[off+1]<<8)|(d[off+2]<<16); st=d[off+3]
        if size==0xFFFFFF:
            if off+24>end: return
            gd=d[off+4:off+20]; doff,attr=struct.unpack_from("<HH",d,off+20)
            realsize=struct.unpack_from("<I",d,off+20)[0]
            out.append("  "*depth+"[EXTSEC %s guid=%s size=0x%X doff=0x%X]"%(SEC.get(st,hex(st)),g(gd),realsize,doff))
            if st==0x17: walk_fv(d,off+doff,off+realsize,depth+1,out,base)
            nxt = off+realsize
            if nxt<=off: return
            off=(nxt+3)&~3; continue
        if size<4 or off+size>end: return
        body=d[off+4:off+size]
        extra=""
        if st==0x01 and len(body)>=4:
            u,ct=struct.unpack_from("<IB",body,0); extra=" uncomp=0x%X algo=%d"%(u,ct)
        elif st==0x02 and len(body)>=20:
            gd=body[:16]; doff,attr=struct.unpack_from("<HH",body,16)
            extra=" guid=%s doff=0x%X attr=0x%X%s"%(g(gd),doff,attr," <LZMA>" if gd==LZMA_GUID else "")
        elif st==0x18 and len(body)>=16:
            extra=" guid=%s"%g(body[:16])
        out.append("  "*depth+"SEC %-11s size=0x%-6X%s"%(SEC.get(st,hex(st)),size,extra))
        if st==0x17: walk_fv(d,off+4,off+size,depth+1,out,base)
        off=(off+size+3)&~3

def walk_fv(d, start, limit, depth, out, base):
    if start+0x38>len(d) or d[start+0x28:start+0x2C]!=b"_FVH": return
    fvlen=struct.unpack_from("<Q",d,start+0x20)[0]; hlen=struct.unpack_from("<H",d,start+0x30)[0]
    extoff=struct.unpack_from("<H",d,start+0x34)[0]
    if fvlen<=0x38 or start+fvlen>len(d): return
    fguid=d[start+0x10:start+0x20]
    fstart=start+hlen
    if extoff:
        extsize=struct.unpack_from("<I",d,start+extoff+16)[0]
        out.append("  "*depth+"[FV +0x%X len=0x%X %s  ext@0x%X sz=0x%X]"%(start-base,fvlen,"FFS2" if fguid==FS2 else g(fguid),extoff,extsize))
        fstart=(start+extoff+extsize+7)&~7
    else:
        out.append("  "*depth+"[FV +0x%X len=0x%X %s]"%(start-base,fvlen,"FFS2" if fguid==FS2 else g(fguid)))
    off=fstart; endfv=start+fvlen; n=0
    while off+24<=endfv:
        if d[off:off+16]==b"\xff"*16 and d[off+16:off+24]==b"\xff"*8:
            out.append("  "*(depth+1)+"... 空闲 0x%X 字节"%(endfv-off)); break
        fg=d[off:off+16]; ftype=d[off+18]; fattr=d[off+19]
        fsize=d[off+20]|(d[off+21]<<8)|(d[off+22]<<16); state=d[off+23]
        if fsize<24 or off+fsize>endfv:
            out.append("  "*(depth+1)+"!! 异常 size=0x%X @+0x%X type=%02X"%(fsize,off-base,ftype)); break
        out.append("  "*(depth+1)+"F %-11s %s sz=0x%-6X at+0x%X"%(FFS_TYPES.get(ftype,hex(ftype)),g(fg),fsize,off))
        walk_sections(d,off+24,off+fsize,depth+2,out,base)
        off=(off+fsize+7)&~7; n+=1
    return

if __name__=="__main__":
    data=open(sys.argv[1],"rb").read(); base=int(sys.argv[3],16) if len(sys.argv)>3 else 0
    out=[]; n=0
    for o in range(0,len(data)-0x40,8):
        if data[o+0x28:o+0x2C]==b"_FVH" and data[o:o+16]==b"\0"*16:
            fvlen=struct.unpack_from("<Q",data,o+0x20)[0]
            if 0x40<fvlen<=len(data)-o: walk_fv(data,o,len(data),0,out,base); n+=1
    print("FV=%d 行=%d"%(n,len(out)))
    open(sys.argv[2] if len(sys.argv)>2 else "tree.txt","w",encoding="utf-8").write("\n".join(out))
    print("\n".join(out[:200]))
