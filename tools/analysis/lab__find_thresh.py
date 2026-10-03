import re, struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
DUMP=r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"
REC=1084
data=open(BIN,"rb").read()
mem=bytearray(0x10000)
for line in open(DUMP,encoding="utf-8",errors="replace"):
    m=re.match(r"^0x([0-9A-F]{4})\s+([0-9A-F ]+)$",line.strip())
    if m:
        a=int(m.group(1),16); b=bytes.fromhex(m.group(2)); mem[a:a+len(b)]=b

print("=== 在配置记录(0-4)中找 16 位值 ≈141(按下) / ≈97(松开) ===")
for i in range(5):
    r=data[i*REC:(i+1)*REC]
    hits=[]
    for k in range(0,REC-1,1):
        v=struct.unpack_from("<H",r,k)[0]
        if 130<=v<=152 or 88<=v<=104:
            hits.append((k,v))
    print(f"  记录{i}: {len(hits)} 处")
    for k,v in hits[:20]:
        ctx=" ".join(f"{x:02X}" for x in r[max(0,k-4):k+6])
        print(f"     +0x{k:03X} = {v:5d} (0x{v:04X})  上下文 {ctx}")
print("\n=== 在传感器 64KB 空间找相同候选 ===")
hits=[]
for k in range(0,0xFFFE):
    v=struct.unpack_from("<H",mem,k)[0]
    if 130<=v<=152 or 88<=v<=104:
        hits.append((k,v))
print(f"  共 {len(hits)} 处 (太多说明该方法不够特异, 下面按'是否落在配置映射区'过滤)")
# 配置映射区(从 rosetta2 得到)
regions=[(0x5E06,0x5E06+0x440),(0xA34C,0xA34C+0x100),(0xBD7E,0xBD7E+0x100),(0xBDBE,0xBDBE+0x100),
         (0x5388,0x5388+0x200),(0x5948,0x5948+0x200),(0x5988,0x5988+0x200),(0x59C8,0x59C8+0x200),
         (0x2CB1,0x2CB1+0x100),(0x5A08,0x5A08+0x200),(0x5B96,0x5B96+0x200),(0x2D50,0x2D50+0x200),
         (0x5D3E,0x5D3E+0x100),(0x5E3E,0x5E3E+0x100)]
print("\n  落在已知配置映射区内的候选:")
cnt=0
for k,v in hits:
    for a,b in regions:
        if a<=k<b:
            print(f"     0x{k:04X} = {v:5d} (0x{v:04X})  [映射区 0x{a:04X}]")
            cnt+=1
            break
    if cnt>40: break
print(f"    共 {cnt} 处")
