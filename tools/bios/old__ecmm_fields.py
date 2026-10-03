"""精确解析 ECMM Field，输出 (位偏移, 字段名, 位宽)，并定位 ERCD 用到的寄存器。"""
import re, struct
d=open("out/DSDT-528KB.bin","rb").read()
def pkglen(b,i):
    lead=b[i]; n=lead>>6
    if n==0: return lead & 0x3F, 1
    v=lead & 0x0F
    for k in range(n): v |= b[i+1+k] << (4+8*k)
    return v, 1+n

# 找 Field(ECMM)
out=[]
i=0
while i < len(d)-8:
    if d[i]==0x5B and d[i+1]==0x81:          # FieldOp
        pl,pn = pkglen(d,i+2)
        no=i+2+pn
        nm=d[no:no+4]
        if nm==b"ECMM":
            # FieldFlags 1 字节，然后字段列表直到 i+2+pl
            p=no+5
            end=i+2+pl
            off=0
            rows=[]
            while p<end:
                if d[p]==0x00:
                    ln,p2=pkglen(d,p+1)
                    rows.append((off,"<Reserved>",ln)); off+=ln; p+=1+p2; continue
                seg=d[p:p+4]
                if not re.fullmatch(rb"[A-Z_][A-Z0-9_]{3}", seg): break
                p+=4
                ln,p2=pkglen(d,p)
                bits = ln+1 if ln<4 else ln
                rows.append((off,seg.decode('latin1'),bits)); off+=bits; p+=1+p2
            out.append((i,pl,rows,off))
        i+=1
    else: i+=1

print("找到 ECMM Field 定义 %d 处"%len(out))
for st,pl,rows,tot in out:
    print("\n### Field @0x%X  PkgLen=0x%X  字段数=%d  总位数=%d (0x%X)  总字节=0x%X"%(
        st,pl,len(rows),tot,tot,(tot+7)//8))
    for o,nm,bits in rows:
        print("   %5d位 (%4d)  字节0x%03X.%d  %-10s %3d位"%(o,o,o//8,o%8,nm,bits))
    # 定位关键寄存器
    keys=("ECMD","EDT1","EDT2","EDT3","EDT4","EDT5","ECTB","ECTE","ESRC","ERN1","ERN2","ERN3","ERN4","ERN5","ERN6","ERN7","ERN8","LIDF","LESR","LSRN")
    print("   --- 关键寄存器位置 ---")
    for o,nm,bits in rows:
        if nm in keys:
            print("      %-6s 位偏移 %5d -> 字节 0x%03X (位 %d)  %d 位   在 768B 窗口内: %s"%(
                nm,o,o//8,o%8,bits,"是 ✔" if o//8 < 0x300 else "否 ✘"))
