# -*- coding: utf-8 -*-
import struct, collections, math, zlib, time
K = open("<WORKSPACE>",'rb').read()
K316 = K[316:]+K[:316]
d = open("bios-re/GT7868Q_native_fw.bin",'rb').read()
def parse(buf):
    for o in range(0, min(len(buf)-300, 65536)):
        s = struct.unpack('>I', buf[o:o+4])[0]
        if 1000 < s <= len(buf)-o and sum(buf[o+6:o+6+s]) & 0xFFFF == struct.unpack('>H', buf[o+4:o+6])[0]:
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
ALL=b"".join(x for _,_,_,x in BL)

def ngset(b,n=12): return {b[i:i+n] for i in range(len(b)-n+1)}
BLG=[ngset(x) for _,_,_,x in BL]
ALLG=ngset(ALL)

tab={}
tbl=[]
for i in range(256):
    c=i
    for _ in range(8): c=(c>>1)^(0xEDB88320 if c&1 else 0)
    tbl.append(c)
tab["CRC32-IEEE u32LE"]=b"".join(struct.pack('<I',v) for v in tbl)
tab["CRC32-IEEE u32BE"]=b"".join(struct.pack('>I',v) for v in tbl)
t2=[]
for i in range(256):
    c=i<<8
    for _ in range(8): c=((c<<1)^0x1021)&0xFFFF if c&0x8000 else (c<<1)&0xFFFF
    t2.append(c)
tab["CRC16-CCITT u16LE"]=b"".join(struct.pack('<H',v) for v in t2)
tab["CRC16-CCITT u16BE"]=b"".join(struct.pack('>H',v) for v in t2)
SB=bytes.fromhex("637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b27509832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cfd0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdbe0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9ee1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16")
tab["AES S-box"]=SB
IV=bytearray(256)
for i,v in enumerate(SB): IV[v]=i
tab["AES S-box inv"]=bytes(IV)
tab["sin u8 256点"]=bytes(int(round(127.5+127.5*math.sin(2*math.pi*i/256)))&0xFF for i in range(256))
tab["sin u16LE 4096点"]=b"".join(struct.pack('<H',int(round(32767+32767*math.sin(2*math.pi*i/4096)))) for i in range(4096))
tab["Gray 0..255"]=bytes(i^(i>>1) for i in range(256))
tab["递增 0..255"]=bytes(range(256))
tab["K 本体"]=K
tab["rot_left(K,316)"]=K316
tab["K 重复4次"]=K*4

print("=== Q1-2. 已知表对照：统计「该表的 12 字节窗口」在 13 块明文里命中多少 ===")
print("（12 字节窗口在 100 KB 随机数据里的期望命中数 ≈ 0）")
print("%-22s %-9s %-11s %-9s %s"%("已知表","窗口数","命中块数","命中窗口","判定"))
for nm,T in tab.items():
    g=ngset(T); hit=0; blk=0
    for s in BLG:
        h=len(g & s)
        if h: blk+=1; hit+=h
    print("%-22s %-9d %-11d %-9d %s"%(nm,len(g),blk,hit,"★命中" if hit else "无命中"))
print()
print("=== Q1-3. 明文的均匀性 ===")
for (i,t,ln,x) in BL:
    nz=bytes(c for c in x if c!=0)
    if len(nz)<400: 
        print("  块%-2d t=0x%02x  [空白/近空白]"%(i,t)); continue
    c=collections.Counter(nz); exp=len(nz)/256
    chi=sum((c.get(v,0)-exp)**2/exp for v in range(256))
    u16=sorted(int.from_bytes(x[j:j+2],'little') for j in range(0,ln-1,2))
    print("  块%-2d t=0x%02x  非零H0=%.3f chi2=%7.1f(均匀=255) u16 p50=%-6d p90=%-6d p99=%-6d"
          %(i,t,-sum(v/len(nz)*math.log2(v/len(nz)) for v in c.values()),chi,
            u16[len(u16)//2],u16[int(len(u16)*0.9)],u16[int(len(u16)*0.99)]))
print("  ⇒ CRC/S-box/sin 这类表：H0 4–6、chi2 远>1500、值域有界、且会在文件里以连续表形式出现")
print()
print("=== Q1-4. ★ 对照样本 GT7936L（LVFS 2026 新族）载荷是否也近均匀 ===")
gl=open("vendor/goodix-lvfs/GT7936L_16753412.bin",'rb').read()
print("  文件 %d B 头: %s | %r"%(len(gl),gl[:20].hex(' '),gl[:16]))
for lo,hi,nm in [(0,0x1000,"0x00000-0x01000"),(0x1000,0x8000,"0x01000-0x08000"),
                 (0x8000,0x20000,"0x08000-0x20000"),(0x20000,0x30000,"0x20000-0x30000"),
                 (0x30000,len(gl),"0x30000-end")]:
    seg=gl[lo:hi]
    if len(seg)<64: continue
    c=collections.Counter(seg)
    print("  %-18s H0=%.4f 零%5.1f%% FF%5.1f%% zlib=%.4f  u16p99=%d"
          %(nm,-sum(v/len(seg)*math.log2(v/len(seg)) for v in c.values()),
            100*seg.count(0)/len(seg),100*seg.count(0xff)/len(seg),
            len(zlib.compress(seg,9))/len(seg),
            sorted(int.from_bytes(seg[j:j+2],'little') for j in range(0,len(seg)-1,2))[int(len(seg)/2*0.99)]))
print()
print("=== Q1-5. 载荷A 明文 vs GT7936L 载荷：有没有公共片段 ===")
for lo,hi in [(0x1000,0x8000),(0x8000,0x20000),(0x20000,0x30000)]:
    g=ngset(gl[lo:hi])
    hit=len(g & ALLG)
    print("  GT7936L[0x%X:0x%X] 12B 窗口在载荷A明文里命中 %d"%(lo,hi,hit))
