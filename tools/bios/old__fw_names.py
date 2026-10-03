import struct, re, sys, collections
d=open("fw_decompressed.bin","rb").read()
FS2=bytes.fromhex("78e58c8c3d8a1c4f9935896185c32dd3")
def g(b):
    a,b2,c=struct.unpack_from("<IHH",b,0)
    return "%08X-%04X-%04X-%s-%s"%(a,b2,c,b[8:10].hex().upper(),b[10:16].hex().upper())
def uistr(body):
    # UI section: UTF-16LE string
    try:
        s=body.decode("utf-16-le",errors="ignore")
    except: return ""
    s="".join(ch for ch in s if ch.isprintable())
    return s
files=[]   # (guid, type, off, size, name, sections[])
def walk_sections(off,end,acc):
    while off+4<=end:
        size=d[off]|(d[off+1]<<8)|(d[off+2]<<16); st=d[off+3]
        if size==0xFFFFFF:
            gd=d[off+4:off+20]; doff,attr=struct.unpack_from("<HH",d,off+20)
            realsize=struct.unpack_from("<I",d,off+20)[0]
            acc.append((st,gd,off,realsize)); off=(off+realsize+3)&~3; continue
        if size<4 or off+size>end: return
        acc.append((st,None,off,size))
        off=(off+size+3)&~3
def walk_fv(start):
    fvlen=struct.unpack_from("<Q",d,start+0x20)[0]; hlen=struct.unpack_from("<H",d,start+0x30)[0]
    extoff=struct.unpack_from("<H",d,start+0x34)[0]
    fs=start+hlen
    if extoff:
        extsize=struct.unpack_from("<I",d,start+extoff+16)[0]
        fs=(start+extoff+extsize+7)&~7
    off=fs; endfv=start+fvlen
    while off+24<=endfv:
        if d[off:off+16]==b"\xff"*16 and d[off+16:off+24]==b"\xff"*8: break
        fg=d[off:off+16]; ft=d[off+18]; fsz=d[off+20]|(d[off+21]<<8)|(d[off+22]<<16)
        if fsz<24 or off+fsz>endfv: break
        acc=[]; walk_sections(off+24,off+fsz,acc)
        name=""
        for st,gd,s2,sz2 in acc:
            if st==0x15: name=uistr(d[s2+4:s2+sz2])
        files.append((g(fg),ft,off,fsz,name,acc))
        off=(off+fsz+7)&~7
walk_fv(0x80)
print("文件总数 = %d"%len(files))
print("\n=== 前 80 个模块名 (UI 段) ===")
n=0
for guid,ft,off,fsz,name,acc in files:
    if name:
        n+=1
        if n<=80: print("  %-11s %s  sz=0x%-6X %s"%({0x07:"DXE_DRV",0x06:"PEIM",0x05:"DXE_CORE",0x04:"PEI_CORE",0x03:"SEC",0x09:"APP",0x0A:"MM",0x0D:"MM_CORE",0x0B:"FV_IMG",0x01:"RAW",0x02:"FREEFORM",0x0E:"MM_STD"}.get(ft,hex(ft)),guid,fsz,name))
print("有名字的文件数 = %d"%n)
print("\n=== 非驱动类文件 (RAW/FREEFORM/FV_IMAGE/APP) ===")
for guid,ft,off,fsz,name,acc in files:
    if ft in (0x01,0x02,0x0B,0x09,0xF0):
        seclist=",".join(hex(s[0]) for s in acc[:6])
        print("  type=%-9s %s sz=0x%-7X @0x%-8X secs=[%s] name=%r"%(
            {0x01:"RAW",0x02:"FREEFORM",0x0B:"FV_IMAGE",0x09:"APP",0xF0:"PAD"}.get(ft,hex(ft)),guid,fsz,off,seclist,name[:50]))
import pickle
pickle.dump(files,open("files.pkl","wb"))
