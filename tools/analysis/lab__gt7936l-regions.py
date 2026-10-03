import collections,math
p=r"<LAB>\touchpad-lab\poc\pkg\gt7936l\GT7936L_16753412.bin"
b=open(p,"rb").read()
def H(d):
    if not d: return 0
    c=collections.Counter(d); n=len(d)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
print("=== 文件各区域概览 ===")
for lo,hi in [(0,0x1000),(0x1000,0x2000),(0x2000,0x1F000),(0x1F000,0x30000),(0x30000,0x3E000),(0x3E000,0x3F018)]:
    seg=b[lo:min(hi,len(b))]
    print(f"  0x{lo:06X}-0x{hi:06X}  {len(seg):7d} B  熵={H(seg):.3f}")
print()
print("=== 配置区样本：0x1F000 / 0x21000 / 0x23000 各前 128 字节 ===")
for lo in (0x1F000,0x21000,0x23000,0x25000):
    print(f"\n-- 0x{lo:06X} --")
    for o in range(lo,lo+128,16):
        seg=b[o:o+16]
        print(f"   0x{o:06X}: "+' '.join(f'{x:02x}' for x in seg)+"  "+''.join(chr(x) if 32<=x<127 else '.' for x in seg))
print()
print("=== 9 个配置分区是否相同？(逐块比对 0x2000) ===")
addrs=[0x1F000,0x21000,0x23000,0x25000,0x27000,0x29000,0x2B000,0x2D000,0x2F000]
base=b[0x1F000:0x21000]
for a in addrs[1:]:
    seg=b[a:a+0x2000]
    same=sum(1 for i in range(min(len(base),len(seg))) if base[i]==seg[i])
    print(f"  0x{a:06X} vs 0x1F000: 相同 {same}/{len(seg)} = {100*same/len(seg):.1f}%")
print()
print("=== 0x30000 之后是什么（分区表未覆盖的 6 万字节）===")
for o in range(0x30000,0x30080,16):
    seg=b[o:o+16]
    print(f"   0x{o:06X}: "+' '.join(f'{x:02x}' for x in seg)+"  "+''.join(chr(x) if 32<=x<127 else '.' for x in seg))
print()
print("=== 0x3E248 附近（第二次出现 '7936L'）===")
for o in range(0x3E240,0x3E2A0,16):
    seg=b[o:o+16]
    print(f"   0x{o:06X}: "+' '.join(f'{x:02x}' for x in seg)+"  "+''.join(chr(x) if 32<=x<127 else '.' for x in seg))
