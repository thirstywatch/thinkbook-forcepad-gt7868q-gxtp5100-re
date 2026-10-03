# -*- coding: utf-8 -*-
"""把配置体按 TLV 展开成全表；并做起点/打乱对照"""
import struct, collections, random, math
d=open("bios-re/GT7868Q_native_fw.bin",'rb').read()
BODY=d[0x4C:0x4C+1024]; TAIL=d[0x4C+1024:0x4C+1084]
def walk(buf,start=0):
    i=start; out=[]
    while i<len(buf):
        if i+2>len(buf): break
        tag=buf[i]; ln=buf[i+1]
        if i+2+ln>len(buf):
            out.append((i,tag,ln,'TRUNC')); break
        out.append((i,tag,ln,buf[i+2:i+2+ln])); i+=2+ln
    return out
def cov(buf,start=0):
    w=walk(buf,start); 
    return sum(2+(0 if x[3]=='TRUNC' else x[2]) for x in w), len(w)
print("=== 起点扫描（找覆盖率最高且显著高于打乱对照的起点）===")
print("%-6s %-9s %-9s %-9s %s"%("起点","覆盖","覆盖率","块数","打乱对照覆盖率(20次均)"))
best=None
for st in range(0,16):
    c,n=cov(BODY,st); r=c/len(BODY)
    rs=[]
    for _ in range(20):
        y=bytearray(BODY); random.shuffle(y); rs.append(cov(bytes(y),st)[0]/len(BODY))
    rm=sum(rs)/len(rs)
    flag="★" if r>rm+0.10 else ("+" if r>rm+0.03 else "")
    print("%-6d %-9d %-9.1f%% %-9d %.1f%%  %s"%(st,c,r*100,n,rm*100,flag))
    if best is None or r-rm>best[3]: best=(st,c,n,r-rm)
print("\n最优起点 = %d  (超出打乱对照 %.1f pt)"%(best[0],best[3]*100))
ST=best[0]
print()
print("=== 配置体 TLV 全表（起点 %d）==="%ST)
print("%-6s %-6s %-5s %-8s %s"%("偏移","TAG","LEN","类型","payload 摘要"))
w=walk(BODY,ST)
for off,tag,ln,pl in w:
    if pl=='TRUNC': print("%-6s 0x%02X   %-5d %-8s TRUNC"%(hex(off),tag,ln,'')); continue
    vals=list(pl)
    u8=collections.Counter(vals)
    kind=[]
    if all(0x20<=v<0x7f for v in vals) and len(vals)>=3: kind.append("ASCII")
    if all(v not in (0,0xff) for v in vals) and len(vals)>=4:
        nondec=all(vals[i]<=vals[i+1] for i in range(len(vals)-1))
        noninc=all(vals[i]>=vals[i+1] for i in range(len(vals)-1))
        if nondec: kind.append("单调↑")
        if noninc: kind.append("单调↓")
    if len(pl)%2==0:
        be=[int.from_bytes(pl[i:i+2],'big') for i in range(0,len(pl),2)]
        le=[int.from_bytes(pl[i:i+2],'little') for i in range(0,len(pl),2)]
        if all(v<4096 for v in be): kind.append("BE16小值")
        if all(v<4096 for v in le): kind.append("LE16小值")
    if len(set(vals))==1: kind.append("常量")
    top=",".join("%d×%d"%(v,c) for v,c in u8.most_common(3))
    print("%-6s 0x%02X   %-5d %-8s %s"%(hex(off),tag,ln,"/".join(kind) or "-",
          pl[:20].hex(' ')+(" ..."%"" if ln>20 else "")+"   ["+top+"]"))
