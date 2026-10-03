import struct, math, os
PATH = r"<WORKSPACE>"
data = open(PATH,"rb").read(); N=len(data)
def shannon(d):
    if not d: return 0.0
    c=[0]*256
    for b in d: c[b]+=1
    n=len(d); e=0.0
    for x in c:
        if x: p=x/n; e-=p*math.log2(p)
    return e
# 熵剖面
ents=[]
for off in range(0, N-2048, 2048):
    ents.append((off, shannon(data[off:off+2048])))
hi=max(e[1] for e in ents); lo=min(e[1] for e in ents)
bnd=None
for i in range(1,len(ents)):
    if ents[i-1][1]>7.3 and ents[i][1]<6.0:
        bnd=ents[i][0]; break
print("文件大小:", N, "熵范围: %.2f..%.2f"%(lo,hi))
print("高->低熵边界:", hex(bnd) if bnd else "无")
# 向量表
def vt(o):
    sp=struct.unpack_from("<I",data,o)[0]; rst=struct.unpack_from("<I",data,o+4)[0]
    return sp,rst
sp,rst=vt(bnd if bnd else 0x19ABC)
print("TF100A 段起点(0x19ABC) SP=%s Reset=%s"%(hex(sp),hex(rst)))
print("  SP∈0x20000000? ", 0x20000000<=sp<=0x20010000, " Reset∈0x08000000+Thumb?", (rst&0xFF000000==0x08000000)and(rst&1))
