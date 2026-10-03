import sys,os,collections,math
p=r"<WORKSPACE>"
b=open(p,"rb").read()
print("文件",len(b))
# 分块：明文头(0..0x1000) / 加扰主体(0x1000..0x18000)
for name,lo,hi in [("明文头",0x0,0x1000),("加扰主体",0x1000,0x18000),("尾部",0x18000,min(len(b),0x1A000))]:
    seg=b[lo:hi]
    # 16 字节块重复统计
    blocks=collections.Counter(seg[i:i+16] for i in range(0,len(seg)-15,16))
    tot=sum(blocks.values()); rep=tot-sum(1 for v in blocks.values() if v==1)
    print(f"\n[{name}] 0x{lo:X}..0x{hi:X}  {len(seg)} B  16B块数={tot}")
    print(f"   重复块占比: {rep}/{tot} = {100*rep/tot:.2f}%   不同块数={len(blocks)}")
    if blocks:
        top=blocks.most_common(3)
        print(f"   最高频块: " + " | ".join(f"{v.hex()}×{c}" for v,c in top if c>1) if any(c>1 for _,c in top) else "   （无重复块）")
    # 字节直方图熵
    c=collections.Counter(seg); H=-sum((v/len(seg))*math.log2(v/len(seg)) for v in c.values())
    print(f"   字节熵={H:.4f}   不同字节值={len(c)}/256")
    # 单字节周期性检查（是否有 256 周期或固定 XOR 的痕迹）
    # 统计每 16 字节位置的字节分布（ECB 下每个位置独立）
    for pos in range(4):
        cc=collections.Counter(seg[i+pos] for i in range(0,len(seg)-15,16))
        print(f"     块内偏移{pos}: 不同值={len(cc)}  最高频={cc.most_common(1)[0][0]:02x}×{cc.most_common(1)[0][1]}")
