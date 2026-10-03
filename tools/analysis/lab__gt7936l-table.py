import struct,collections
p=r"<LAB>\touchpad-lab\poc\pkg\gt7936l\GT7936L_16753412.bin"
b=open(p,"rb").read()
print("文件",len(b))
# 找 03 00 20 00 的所有出现及间距
occ=[]
i=0
while True:
    i=b.find(b'\x03\x00\x20\x00',i)
    if i<0: break
    occ.append(i); i+=1
print("\n=== '03 00 20 00' 出现位置（前 30）===")
print("  ", [hex(x) for x in occ[:30]])
if len(occ)>2:
    diffs=[occ[k+1]-occ[k] for k in range(len(occ)-1)]
    print("  间距分布:", collections.Counter(diffs).most_common(8))
print("\n=== 头部按推测格式解析（type 低字节 + size 3 字节小端 + addr 4 字节）===")
# 从 0x28 开始试 stride 8
for start in (0x28,0x2c,0x30,0x34,0x40,0x44):
    print(f"\n--- 起点 0x{start:X}, stride 8 ---")
    for k in range(8):
        o=start+k*8
        if o+8>len(b): break
        a,bb=struct.unpack_from("<II",b,o)
        t=a&0xff; sz=(a>>8)&0xffffff
        print(f"   [{k}] @0x{o:04X}  word0=0x{a:08X} (type={t}, size=0x{sz:X})  word1=0x{bb:08X}")
print("\n=== 全文件搜 'type=3,size=0x2000' 这一族（0x00200003）及邻近 ===")
occ2=[]; i=0
while True:
    i=b.find(b'\x03\x00\x20\x00',i)
    if i<0: break
    occ2.append(i); i+=1
for o in occ2[:12]:
    seg=b[max(0,o-8):o+16]
    print(f"   @0x{o:04X}: "+' '.join(f'{x:02x}' for x in seg))
