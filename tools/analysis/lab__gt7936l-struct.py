import re,collections,math
p=r"<LAB>\touchpad-lab\poc\pkg\gt7936l\GT7936L_16753412.bin"
b=open(p,"rb").read()
print("=== 头部 128 字节逐 4 字节解读 ===")
import struct
for o in range(0,128,4):
    v=struct.unpack_from("<I",b,o)[0]
    print(f"  0x{o:04X} = 0x{v:08X} ({v})")
print()
print("=== 找与本机同类的结构：YELSTO / 7868Q / 8字节子系统表 ===")
for k in [b'YELSTO',b'BERLIN',b'7936L',b'Goodix',b'GOODIX',b'GT79',b'7868',b'TF100']:
    idx=[];i=0
    while True:
        i=b.find(k,i)
        if i<0:break
        idx.append(hex(i)); i+=1
    print(f"  {k!r:12} -> {len(idx)}  {idx[:6]}")
print()
print("=== 搜我们已知的子表模式  03 00 00 20 ...（type=3,size=0x2000）===")
n=0
for i in range(0,len(b)-8):
    if b[i]==0x03 and b[i+1]==0x00 and b[i+2]==0x00 and b[i+3]==0x20:
        n+=1
        if n<=5: print(f"   @0x{i:X}: "+' '.join(f'{x:02x}' for x in b[i:i+16]))
print(f"  共 {n} 处")
print()
print("=== 找 RISC-V 向量表特征（0x00000000 段 + 跳转）===")
print("  0x0000-0x0080:")
for o in range(0,0x80,16):
    print(f"    0x{o:04X}: "+' '.join(f'{x:02x}' for x in b[o:o+16]))
print()
print("=== 全文件 ASCII 串按长度排（>=10）===")
strs=[m.group(0) for m in re.finditer(rb'[\x20-\x7e]{10,}', b)]
print(f"  共 {len(strs)} 个")
for x in strs[:30]: print("   ",x.decode('latin1')[:110])
