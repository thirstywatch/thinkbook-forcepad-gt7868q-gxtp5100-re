import re, struct, sys
d=open("out/DSDT-528KB.bin","rb").read()
def pkglen(b,i):
    lead=b[i]; n=lead>>6
    if n==0: return lead & 0x3F, 1
    v=lead & 0x0F
    for k in range(n): v |= b[i+1+k] << (4+8*k)
    return v, 1+n
want=sys.argv[1:]
i=0
found={}
while i < len(d)-8:
    if d[i]==0x14:
        pl,pn = pkglen(d,i+1); off=i+1+pn
        nm=d[off:off+4]
        if re.fullmatch(rb"[A-Z_][A-Z0-9_]{3}", nm):
            n=nm.decode()
            if n in want: found.setdefault(n,[]).append((i,pl,pn,off,d[off+4]))
        i+=1
    else: i+=1
for n in want:
    for (st,pl,pn,no,flags) in found.get(n,[]):
        argc=flags & 0x07
        be=st+1+pl
        print("\n"+"="*76)
        print("### %s  @0x%X  PkgLen=0x%X  ArgCount=%d  Serialize=%d  体 0x%X..0x%X (%d B)"%(
            n,st,pl,argc,1 if flags&8 else 0,no+5,be,be-(no+5)))
        s=d[no+5:be]
        for k in range(0,len(s),16):
            x=s[k:k+16]
            print("   +%03X  %s  |%s|"%(k," ".join("%02X"%c for c in x),"".join(chr(c) if 32<=c<127 else "." for c in x)))
    if n not in found: print("\n### %s 未找到"%n)
