import struct
p=r"<LAB>\touchpad-lab\poc\pkg\gt7936l\GT7936L_16753412.bin"
b=open(p,encoding=None).read() if False else open(p,"rb").read()
print("GT7936L_16753412.bin  %d B"%len(b))
print()
print("=== 完整分区表（从 0x52 起，步长 10）===")
print(" idx  type   size        flash_addr(x256)   实际地址     备注")
o=0x52; k=0; rows=[]
while o+10<=len(b) and k<40:
    t=b[o]; sz=b[o+1]|(b[o+2]<<8)|(b[o+3]<<16); a=b[o+6]|(b[o+7]<<8)
    if t==0 and sz==0 and a==0: print("   —— 空项，表结束 ——"); break
    addr=a*256
    note=""
    if addr==0x1E000: note="★ 配置数据（与官方 FLASH_ADDR_CONFIG_DATA 同值）"
    if addr==0: note="★ flash 起始（ISP/引导）"
    print(f" {k:3d}  0x{t:02X}  0x{sz:08X}  0x{a:04X}          0x{addr:06X}    {note}")
    rows.append((t,sz,addr))
    o+=10; k+=1
print(f"\n  共 {len(rows)} 项")
tot=sum(r[1] for r in rows)
print(f"  size 合计 = 0x{tot:X} = {tot} B   文件大小 = {len(b)} B")
print()
print("=== 分区按地址排序 ===")
for t,sz,a in sorted(rows,key=lambda r:r[2]):
    print(f"  0x{a:06X}  size=0x{sz:06X} ({sz:6d} B)  type=0x{t:02X}")
print()
print("=== 头部其它字段 ===")
for o2 in range(0,0x28,4):
    v=struct.unpack_from("<I",b,o2)[0]
    print(f"  0x{o2:02X} = 0x{v:08X} ({v})")
print()
print("=== 与 7936L 标签相邻的字段（0x0C-0x28）===")
print('  hex:',' '.join(f'{x:02x}' for x in b[0x0c:0x28]))
