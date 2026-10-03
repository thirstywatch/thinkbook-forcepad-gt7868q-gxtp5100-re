import struct, sys, lzma, io, os, zlib

FS2 = bytes.fromhex("78e58c8c3d8a1c4f9935896185c32dd3")
def g(b):
    d1,d2,d3 = struct.unpack_from("<IHH",b,0)
    return "%08X-%04X-%04X-%s-%s"%(d1,d2,d3,b[8:10].hex().upper(),b[10:16].hex().upper())

SEC_TYPES={0x01:"COMPRESSION",0x02:"GUID_DEFINED",0x03:"DISPOSABLE",0x10:"PE32",0x11:"PIC",
 0x12:"TE",0x13:"DXE_DEPEX",0x14:"VERSION",0x15:"UI",0x16:"COMPAT16",0x17:"FV_IMAGE",
 0x18:"FREEFORM_GUID",0x19:"RAW",0x1B:"PEI_DEPEX",0x1C:"SMM_DEPEX"}
FFS_TYPES={0x01:"SECURITY_CORE",0x02:"PEI_CORE",0x03:"DXE_CORE",0x04:"PEI_MODULE",0x05:"DXE_DRIVER",
 0x06:"DXE_RUNTIME",0x07:"DXE_SAL",0x08:"DXE_SMM",0x09:"SMM_CORE",0x0A:"PEIM",0x0B:"MM_STANDALONE",
 0x0C:"MM_CORE",0x0D:"SMM_STANDALONE",0x0E:"APPLICATION",0x0F:"FREEFORM",0xF0:"FV_IMAGE_PAD"}

def parse_sections(data, off, end, depth, out, tag=""):
    """walk sections inside a file body"""
    while off + 4 <= end:
        size = data[off] | (data[off+1]<<8) | (data[off+2]<<16)
        stype = data[off+3]
        if size == 0xFFFFFF:
            # extended header
            if off+24 > end: return
            gd = data[off+4:off+20]
            doff, attr = struct.unpack_from("<HH", data, off+20)
            total = struct.unpack_from("<I", data, off+20+4)[0] if False else None
            out.append(("  "*depth+"EXT-SEC %s guid=%s doff=0x%X attr=0x%X"%(SEC_TYPES.get(stype,hex(stype)),g(gd),doff,attr),off,None))
            # size is stored in the extension: last 4 bytes? spec: Size in ext header at off+20? handled loosely
            break
        if size < 4 or off+size > end: return
        body = data[off+4:off+size]
        name = SEC_TYPES.get(stype, hex(stype))
        extra = ""
        if stype in (0x10,0x12) and len(body)>0x40:
            try:
                mz = body[:2]
                extra = " hdr=%s"%mz
            except: pass
        out.append(("  "*depth+"SEC %-14s size=0x%-7X%s"%(name,size,extra),off,size))
        if stype == 0x17:  # FV_IMAGE -> nested FV
            parse_fv(data, off+4, off+size, depth+1, out)
        elif stype == 0x01:  # COMPRESSION
            if len(body)>=4:
                uncomp, ctype = struct.unpack_from("<IB", body, 0)
                out.append(("  "*depth+"   COMPRESSION uncomp=0x%X type=%d"%(uncomp,ctype),off,None))
        elif stype == 0x02:  # GUID_DEFINED
            if len(body)>=20:
                gd = body[:16]
                doff, attr = struct.unpack_from("<HH", body, 16)
                out.append(("  "*depth+"   GUID_DEFINED guid=%s doff=0x%X attr=0x%X"%(g(gd),doff,attr),off,None))
        off += (size + 3) & ~3

def parse_fv(data, start, limit, depth, out):
    if start+0x38 > len(data): return
    if data[start+0x28:start+0x2C] != b"_FVH": return
    fvlen = struct.unpack_from("<Q", data, start+0x20)[0]
    hlen  = struct.unpack_from("<H", data, start+0x30)[0]
    guid  = data[start+0x10:start+0x20]
    if fvlen <= 0x38 or start+fvlen > len(data): return
    fs = "FFS2" if guid==FS2 else g(guid)
    out.append(("  "*depth+"[FV @0x%X len=0x%X hdr=0x%X %s]"%(start,fvlen,hlen,fs),start,fvlen))
    off = start + hlen
    endfv = start + fvlen
    while off + 24 <= endfv:
        fg = data[off:off+16]
        integ = data[off+16]
        ftype = data[off+17]
        fattr = data[off+18]
        fsize = data[off+19] | (data[off+20]<<8) | (data[off+21]<<16)
        state = data[off+22]
        if fsize == 0xFFFFFF and ftype == 0xFF:
            out.append(("  "*(depth+1)+"... free space 0x%X bytes"%(endfv-off),off,None)); break
        if fsize < 24 or off+fsize > endfv:
            out.append(("  "*(depth+1)+"!! bad file size 0x%X at 0x%X (type=%02X)"%(fsize,off,ftype),off,None)); break
        if state != 0xF8 or ftype not in (0xFF,):
            tn = FFS_TYPES.get(ftype, hex(ftype))
            out.append(("  "*(depth+1)+"FILE %-16s %s size=0x%X attr=%02X state=%02X"%(tn,g(fg),fsize,fattr,state),off,fsize))
            parse_sections(data, off+24, off+fsize, depth+2, out)
        off += (fsize + 7) & ~7

if __name__ == "__main__":
    path = sys.argv[1]
    data = open(path,"rb").read()
    print("file %s size=0x%X"%(path,len(data)))
    out=[]
    # find FVs at 8-byte alignment
    n=0
    for o in range(0, len(data)-0x40, 8):
        if data[o+0x28:o+0x2C]==b"_FVH" and data[o:o+16]==b"\0"*16:
            fvlen=struct.unpack_from("<Q",data,o+0x20)[0]
            if 0x40 < fvlen <= len(data)-o:
                parse_fv(data,o,len(data),0,out); n+=1
    print("top-level FV 数 = %d, 行数 = %d"%(n,len(out)))
    with open(sys.argv[2] if len(sys.argv)>2 else "uefi_tree.txt","w",encoding="utf-8") as f:
        for line,off,sz in out:
            f.write(line+"\n")
            print(line)
