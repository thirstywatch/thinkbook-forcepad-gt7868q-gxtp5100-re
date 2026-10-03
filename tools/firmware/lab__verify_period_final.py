# -*- coding: utf-8 -*-
import struct, collections, math
K=open("<WORKSPACE>",'rb').read()
K316=K[316:]+K[:316]
d=open("bios-re/GT7868Q_native_fw.bin",'rb').read()
def parse(buf):
    for o in range(0,min(len(buf)-300,65536)):
        s=struct.unpack('>I',buf[o:o+4])[0]
        if 1000<s<=len(buf)-o and sum(buf[o+6:o+6+s])&0xFFFF==struct.unpack('>H',buf[o+4:o+6])[0]:
            ent=[]
            for i in range(30):
                q=o+0x20+i*8; t=buf[q]; ln=int.from_bytes(buf[q+1:q+5],'big')
                if t==0 and ln==0: break
                ent.append((t,ln))
            return o,ent
o,ent=parse(d); off=o+0x100; BL=[]
for i,(t,ln) in enumerate(ent):
    xr=d[off:off+ln]; off+=ln
    BL.append((i,t,ln,bytes(v^K316[(k+0x100)%1024] for k,v in enumerate(xr))))
def trivial(b, th=2): return len(set(b))<=th
print("=== 1. 重复的 16 字节块：有多少是【平凡块】？===")
for (i,t,ln,x) in BL:
    if ln<0x1000 or x.count(0)/ln>0.9: continue
    nb=ln//16
    blocks=[x[j*16:(j+1)*16] for j in range(nb)]
    c=collections.Counter(blocks)
    dup=[(bl,n) for bl,n in c.items() if n>1]
    dup_blocks=sum(n-1 for _,n in dup)
    triv=sum(n-1 for bl,n in dup if trivial(bl))
    print("  块%-2d 重复块 %3d 个；其中【平凡(<=2种字节)】%3d 个 ⇒ 非平凡重复 %3d 个  %s"
          %(i,dup_blocks,triv,dup_blocks-triv,
            "★非平凡重复⇒ECB 迹象" if dup_blocks-triv>0 else "全部平凡⇒零填充假象"))
    if dup_blocks-triv>0:
        for bl,n in sorted(dup,key=lambda z:-z[1])[:3]:
            if not trivial(bl): print("       %s ×%d"%(bl.hex(' '),n))
print()
print("=== 2. L 剖面（基频判定，修正版）===")
for (i,t,ln,x) in BL:
    if x.count(0)/ln>0.6 or ln<0x1000: continue
    r={L:sum(1 for j in range(ln-L) if x[j]==x[j+L])/(ln-L) for L in (16,32,48,64,80,96,128,256,512,1024)}
    s=" ".join("L%d=%.4f"%(L,r[L]) for L in (16,32,48,64,80,96,128,256,1024))
    tag="16 是基频(32/48 明显更低)" if r[16]>r[32]*1.15 and r[16]>r[48]*1.15 else "衰减平滑"
    print("  块%-2d %s  %s"%(i,s,tag))
print()
print("=== 3. 逐列 mod16 熵 vs 随机对照（同直方图打乱后）===")
import random
random.seed(1)
for (i,t,ln,x) in BL[:4]:
    if ln<0x1000: continue
    def colent(b):
        es=[]
        for j in range(16):
            c=collections.Counter(b[j::16]); n=len(b[j::16])
            es.append(-sum(v/n*math.log2(v/n) for v in c.values()))
        return sum(es)/16
    obs=colent(x)
    sh=[]
    for _ in range(10):
        y=bytearray(x); random.shuffle(y); sh.append(colent(bytes(y)))
    m=sum(sh)/len(sh)
    print("  块%-2d 实测各列平均熵=%.3f  打乱后=%.3f  差=%+.3f  %s"
          %(i,obs,m,obs-m,"★列结构存在" if obs<m-0.05 else "无列结构"))
