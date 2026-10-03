import collections,math,zlib,os
p=r"<LAB>\touchpad-lab\poc\pkg\gt7936l\GT7936L_16753412.bin"
b=open(p,"rb").read()
print("文件",len(b))
def H(d):
    if not d: return 0
    c=collections.Counter(d); n=len(d)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
print("\n=== 头部 64 字节 ===")
print(' '.join(f'{x:02x}' for x in b[:64]))
print('ASCII:',''.join(chr(x) if 32<=x<127 else '.' for x in b[:64]))
print("\n=== 熵剖面（每 4 KB）===")
for o in range(0,min(len(b),0x12000),0x1000):
    print(f"  0x{o:06X}  {H(b[o:o+0x1000]):.3f}")
print("\n=== 已知压缩格式魔数 ===")
pats={'zlib 78 01':b'\x78\x01','zlib 78 9c':b'\x78\x9c','zlib 78 da':b'\x78\xda','gzip':b'\x1f\x8b',
      'LZ4':b'\x04\x22\x4d\x18','zstd':b'\x28\xb5\x2f\xfd','xz':b'\xfd7zXZ','LZMA':b'\x5d\x00\x00',
      'bzip2':b'BZh','lzop':b'\x89LZO','7z':b'7z\xbc\xaf'}
for k,v in pats.items():
    n=0; first=[]
    i=0
    while True:
        i=b.find(v,i)
        if i<0: break
        n+=1
        if len(first)<4: first.append(hex(i))
        i+=1
    print(f"  {k:12} -> {n}  {first}")
print("\n=== 尝试 raw deflate 解压（各起点）===")
best=[]
for off in range(0, min(len(b),0x2000), 1):
    for wbits in (-15, 15, 47):
        try:
            d=zlib.decompressobj(wbits)
            out=d.decompress(b[off:off+200000], 4000000)
            if len(out)>512:
                best.append((len(out),off,wbits))
        except Exception:
            pass
    if off>0x800 and not best and off>0x200: break
best.sort(reverse=True)
if best: print("  命中:", best[:5])
else: print("  无")
print("\n=== 找 ASCII 串（>=6）===")
s=b.decode('latin1')
import re
strs=[m.group(0) for m in re.finditer(r'[\x20-\x7e]{6,}', s)]
print("  共",len(strs),"个")
for x in strs[:25]: print("   ",x)
print("\n=== Thumb 代码密度（push {..,lr} = 半字 0xB5xx）===")
for name,lo,hi in [("0x0-0x1000",0,0x1000),("0x1000-0x8000",0x1000,0x8000),("0x8000-0x20000",0x8000,0x20000),("0x20000-end",0x20000,len(b))]:
    seg=b[lo:hi]
    n=sum(1 for i in range(0,len(seg)-1,2) if (seg[i+1]&0xFE)==0xB4 or (seg[i+1]&0xFF)==0xB5)
    print(f"  {name:16} {len(seg):7d} B   push{{..,lr}} 半字数={n}  密度={n/max(1,len(seg)/2):.5f}")
