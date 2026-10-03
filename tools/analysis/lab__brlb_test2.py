import struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
buf=open(BIN,"rb").read(); n=len(buf)
print(f"文件 {n} 字节; 前 8 字节: {buf[:8].hex(' ')}")

# 后缀 sum8 (mod 65536)
suf=[0]*(n+1)
for i in range(n-1,-1,-1):
    suf[i]=(suf[i+1]+buf[i])&0xFFFF
# 前缀 sum16le
pre=[0]*(n//2+2)
for k in range(0,(n//2)*2,2):
    pre[k//2+1]=(pre[k//2]+struct.unpack_from("<H",buf,k)[0])&0xFFFFFFFF

print("\n=== A) config 组: 找 S 使 buf[S+off] == suf[S+6] ===")
hits=[]
for S in range(8, n-8):
    c=suf[S+6]
    for off in (0,2,4):
        for end in ("<",">"):
            if struct.unpack_from(end+"H",buf,S+off)[0]==c:
                hits.append((S,off,end,c))
print(f"  命中 {len(hits)} 个")
for S,off,end,c in hits[:10]:
    print(f"   S=0x{S:X} ({S}) 校验字段@+{off}({end}) sum8=0x{c:04X}  buf[S:S+8]={buf[S:S+8].hex(' ')}")

print("\n=== B) 主头: sum16le(buf[8:fw]) 是否等于头部某 32 位字段 ===")
found=[]
for fw in range(1024, n, 2):
    c=pre[fw//2]-pre[4]
    if c<0: continue
    for off in (0,2,4):
        for end in ("<",">"):
            if struct.unpack_from(end+"I",buf,off)[0]==c:
                found.append((fw,off,end,hex(c)))
print(f"  命中 {len(found)}: {found[:8]}")

print("\n=== C) 105148 切分点细节 ===")
S=105148
print(f"   buf[S:S+32] = {buf[S:S+32].hex(' ')}")
sp=struct.unpack_from("<I",buf,S)[0]; rh=struct.unpack_from("<I",buf,S+4)[0]
print(f"   解释为向量表: 初始SP=0x{sp:08X}  复位入口=0x{rh:08X}")
print(f"   sum8(buf[S+6:]) = 0x{suf[S+6]:04X}")
print(f"   头部 6 字节 = {buf[:6].hex(' ')} -> BE16[0]=0x{struct.unpack_from('>H',buf,0)[0]:04X} BE16[2]=0x{struct.unpack_from('>H',buf,2)[0]:04X} BE16[4]=0x{struct.unpack_from('>H',buf,4)[0]:04X}")
