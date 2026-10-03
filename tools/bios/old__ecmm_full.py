"""ECMM 完整字段表。★修正：命名字段的 PkgLength 独立，读完应 p += p2（不是 1+p2）。"""
import re
d=open("out/DSDT-528KB.bin","rb").read()
def pkglen(b,i):
    lead=b[i]; n=lead>>6
    if n==0: return lead & 0x3F, 1
    v=lead & 0x0F
    for k in range(n): v |= b[i+1+k] << (4+8*k)
    return v, 1+n

def parse_field(i, verbose=False):
    pl,pn = pkglen(d,i+2); no=i+2+pn
    nm=d[no:no+4].decode('latin1'); p=no+5; end=i+2+pl
    off=0; rows=[]
    while p<end:
        if d[p]==0x00:
            ln,p2=pkglen(d,p+1); rows.append((off,"<Res>",ln)); off+=ln; p+=1+p2; continue
        seg=d[p:p+4]
        if not re.fullmatch(rb"[A-Z_][A-Z0-9_]{3}", seg): break
        p+=4
        ln,p2=pkglen(d,p)
        bits = ln+1 if ln<4 else ln
        rows.append((off,seg.decode('latin1'),bits)); off+=bits; p+=p2     # ★
    return nm, pl, rows, off

defs=[]
i=0
while i<len(d)-8:
    if d[i]==0x5B and d[i+1]==0x81:
        nm,pl,rows,tot = parse_field(i)
        defs.append((i,nm,pl,rows,tot)); i+=1
    else: i+=1
print("Field 定义 %d 处"%len(defs))
for i,nm,pl,rows,tot in defs:
    print("   @0x%X  %-5s PkgLen=0x%-5X 字段=%3d 总位=%5d 总字节=0x%X"%(i,nm,pl,len(rows),tot,(tot+7)//8))

KEY=("ECMD","EDT1","EDT2","EDT3","EDT4","EDT5","ECTB","ECTE","ESRC","ERN1","ERN2","ERN3","ERN4","ERN5","ERN6","ERN7","ERN8",
     "LIDF","LESR","LSRN","ECT1","ECT2","ECT3")
print("\n=== 关键寄存器定位 ===")
for i,nm,pl,rows,tot in defs:
    for o,f,b in rows:
        if f in KEY:
            print("   %-5s  %-6s 位%-6d -> 字节 0x%03X (位%d) %2d位   %s"%(
                nm,f,o,o//8,o%8,b,"★768B窗口内" if o//8<0x300 else "窗口外"))
print("\n=== 完整 ECMM 字段表（只打 ECMM 那个）===")
for i,nm,pl,rows,tot in defs:
    if nm=="ECMM" and len(rows)>50:
        print("### @0x%X  %d 个字段  总字节 0x%X"%(i,len(rows),(tot+7)//8))
        for o,f,b in rows:
            mark = "  <<< 768B 窗口内" if o//8 < 0x300 else ""
            print("   %5d  0x%03X.%d  %-9s %3d位%s"%(o,o//8,o%8,f,b,mark))
