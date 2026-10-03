import struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
buf=open(BIN,"rb").read(); n=len(buf)
def sum16(b):
    s=0
    for x in b: s=(s+x)&0xFFFF
    return s
print(f"文件 {n} 字节; 97*1084={97*1084}; 差={n-97*1084}")
print("前 16 字节 (BE 解释):")
print("   [0:2]=0x%04X [2:4]=0x%04X [4:6]=0x%04X [6:8]=0x%04X" % tuple(struct.unpack_from(">HHHH",buf,0)))
print("   [6:8] 作为 BE16 =", struct.unpack_from(">H",buf,6)[0], " (1084 = 0x43C)")

print("\n=== A) 假设 S = firmware_size+6 = 105148 (97*1084) ===")
S=97*1084
print(f"   buf[S:S+2] (cfg_packlen, BE16) = {struct.unpack_from('>H',buf,S)[0]}   期望 {n-S-6}")
print(f"   buf[S+2:S+4] = {buf[S+2:S+4].hex(' ')}")
print(f"   buf[S+3] (sub_cfg_num?) = {buf[S+3]}")
print(f"   buf[S+4:S+6] (checksum BE16?) = 0x{struct.unpack_from('>H',buf,S+4)[0]:04X}")
print(f"   实际 sum16(buf[S+6:]) = 0x{sum16(buf[S+6:]):04X}")
print(f"   buf[S+6:S+18] = {buf[S+6:S+18].hex(' ')}")
print(f"   校验和匹配: {sum16(buf[S+6:])==struct.unpack_from('>H',buf,S+4)[0]}")

print("\n=== B) 穷举切分点 S, 用官方两条约束过滤 ===")
hits=[]
for S in range(512, n-12):
    packlen=struct.unpack_from(">H",buf,S)[0]
    if n-S != packlen+6: continue
    subnum=buf[S+3]
    cks=struct.unpack_from(">H",buf,S+4)[0]
    if subnum==0: continue
    if sum16(buf[S+6:])==cks:
        hits.append((S,packlen,subnum,cks))
print(f"   命中 {len(hits)} 个: {[(hex(s),pl,sn,hex(c)) for s,pl,sn,c in hits[:6]]}")

print("\n=== C) 主固件头部: 用 sum16(buf[6:6+firmware_size])==checksum 穷举 ===")
found=[]
for size_off in range(0,12):
    for csum_off in range(0,12):
        if abs(size_off-csum_off)<4: continue
        for send in (">","<"):
            fw=struct.unpack_from(send+"I",buf,size_off)[0]
            if not (1000<fw<n): continue
            for cend in (">","<"):
                cks=struct.unpack_from(cend+"H",buf,csum_off)[0]
                if sum16(buf[6:6+fw])==cks: found.append((size_off,send,fw,csum_off,cend,cks))
print(f"   命中 {len(found)}: {found[:5]}")
