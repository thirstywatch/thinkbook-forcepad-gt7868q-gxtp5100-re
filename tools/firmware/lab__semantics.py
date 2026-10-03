# -*- coding: utf-8 -*-
"""语义攻坚：① cfg 头结构 ② TLV 走查+打乱对照 ③ 与 sid*.bin 对齐 ④ 已知阈值定位"""
import struct, collections, math, os, random
d = open("bios-re/GT7868Q_native_fw.bin",'rb').read()
BODY = d[0x4C:0x4C+1024]; TAIL = d[0x4C+1024:0x4C+1084]
CFG="<WORKSPACE>"
SID={n:open(CFG+n,'rb').read() for n in ("sid0.bin","sid2.bin","sid3.bin")}

print("="*94)
print("① cfg 文件头结构（从三份 cfg 归纳；可读字段）")
print("="*94)
print("%-10s %-16s %-10s %-12s %-10s %-12s %-12s"%("文件","+0x00 厂商标","+0x08 型号","+0x10 修订","+0x14 项目","+0x1E 时间戳(LE)","+0x23 日期串"))
for n,b in SID.items():
    v=b[0:8].rstrip(b"\0").decode('latin1','replace')
    pid=b[8:16].rstrip(b"\0").decode('latin1','replace')
    rev=b[16:20].hex(' ')
    proj=b[20:28].rstrip(b"\0").decode('latin1','replace')
    ts=struct.unpack('<I',b[30:34])[0]
    import datetime
    tstr=datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d') if 946684800<ts<2000000000 else "?"
    ds=b[0x23:0x2B].rstrip(b"\0").decode('latin1','replace')
    print("%-10s %-16s %-10s %-12s %-10s %-12s %-12s"%(n,v,pid,rev,proj,"%d %s"%(ts,tstr),ds))

print()
print("="*94)
print("② TLV 走查（[TAG][LEN][payload]）在【配置体】上 + 打乱对照（项目纪律：覆盖率单独不算证据）")
print("="*94)
def tlv_cov(buf,start=0,lenw=1):
    i=start; cov=0; blocks=0; trunc=0
    while i<len(buf):
        if i+1+lenw>len(buf): break
        tag=buf[i]; 
        ln=int.from_bytes(buf[i+1:i+1+lenw],'little')
        if ln==0:
            i+=1+lenw; cov+=1+lenw; blocks+=1; continue
        if i+1+lenw+ln>len(buf): trunc+=1; break
        i+=1+lenw+ln; cov+=1+lenw+ln; blocks+=1
    return cov,blocks,trunc
print("%-12s %-8s %-9s %-9s %-9s %s"%("目标","起点","覆盖字节","覆盖率","块数","打乱对照均值"))
for label,buf in [("配置体",BODY),("60B尾",TAIL)]+[(k,v) for k,v in SID.items()]:
    cov,blk,tr=tlv_cov(buf,0,1)
    rnd=[]
    for _ in range(20):
        y=bytearray(buf); random.shuffle(y)
        rnd.append(tlv_cov(bytes(y),0,1)[0])
    print("%-12s 0x%02X     %-9d %-9.1f%% %-9d %.1f%%%s"%(label,0,cov,cov/max(len(buf),1)*100,blk,
          sum(rnd)/len(rnd)/len(buf)*100, "  ★>打乱" if cov/len(buf)>sum(rnd)/len(rnd)/len(buf)+0.03 else "  ≈打乱"))

print()
print("="*94)
print("③ 配置体 ↔ sid*.bin 对齐：以共享片段为锚，看 sid 侧的 TLV 上下文")
print("="*94)
def lcs_anchor(a,b,minlen=10):
    best=(0,0,0)
    n=len(a)
    for i in range(n-minlen):
        for j in range(len(b)-minlen):
            L=0
            while i+L<n and j+L<len(b) and a[i+L]==b[j+L] and L<400: L+=1
            if L>best[0]: best=(L,i,j)
    return best
for n,b in SID.items():
    L,i,j = lcs_anchor(BODY,b,10)
    print("  %s: 最长公共片段 %d B  体+0x%03X ↔ sid+0x%03X"%(n,L,i,j))
    if L>=10:
        print("     体  :",BODY[max(0,i-16):i+L+16].hex(' '))
        print("     sid :",b[max(0,j-16):j+L+16].hex(' '))
        # 用 TLV 走查 sid，看这个锚落在哪个 TAG 块里
        st=0x38 if n!="sid2.bin" else 0x40
        p=st; hit=None
        while p<len(b):
            if p+2>len(b): break
            tag=b[p]; ln=b[p+1]
            if ln==0: p+=2; continue
            if p+2+ln>len(b): break
            if p<=j<p+2+ln: hit=(hex(tag),ln,p,hex(p)); break
            p+=2+ln
        print("     ⇒ 该锚落在 sid 的 TLV 块内: TAG=%s LEN=%s @0x%X (%s)"%(hit[0],hit[1],hit[2],hit[3]) if hit else "     ⇒ 未落入已解 TLV 块")

print()
print("="*94)
print("④ 已知数值定位（实测点击阈值 140 按下 / 98 抬起；旧假设 70/48；时长常量 128/256/512/1000）")
print("="*94)
T=[140,98,70,48,128,256,512,1000,5000,1400,90,100,112,116,104,60,50,21,14,80,120]
for name,buf in [("配置体",BODY),("60B尾",TAIL)]:
    print("  --- %s ---"%name)
    u8=collections.Counter(buf)
    le=[int.from_bytes(buf[i:i+2],'little') for i in range(len(buf)-1)]
    be=[int.from_bytes(buf[i:i+2],'big')    for i in range(len(buf)-1)]
    cl=collections.Counter(le); cb=collections.Counter(be)
    print("    %-6s %s"%("值"," ".join("%-4d"%t for t in T)))
    print("    %-6s %s"%("u8"," ".join("%-4d"%u8[t] for t in T)))
    print("    %-6s %s"%("LE16"," ".join("%-4d"%cl[t] for t in T)))
    print("    %-6s %s"%("BE16"," ".join("%-4d"%cb[t] for t in T)))
print()
print("  ★ 出现次数最高的那些值（看是不是成组的参数刻度）")
for name,buf in [("配置体",BODY)]:
    u8=collections.Counter(buf)
    le=collections.Counter(int.from_bytes(buf[i:i+2],'little') for i in range(len(buf)-1))
    print("    u8 top20:",[ (v,c) for v,c in u8.most_common(20) if v not in (0,0xff)])
    print("    LE16 top20:",[ (v,c) for v,c in le.most_common(20) if v not in (0,0xffff)])
