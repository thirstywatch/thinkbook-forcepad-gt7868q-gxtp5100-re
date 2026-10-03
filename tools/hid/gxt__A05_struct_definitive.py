# -*- coding: utf-8 -*-
"""A5. 定案：分区表项结构。
逐字节事实（绝对偏移，12 项 × 8 B @0x1164）:
  item0: 03 00 00 20 00 01 60 00
    +0=03 +1=00 +2=00 +3=20 +4=00 +5=01 +6=60 +7=00
观察: 每一字段前面都插了一个 00（字节交织/stride=2）。
  逻辑 16 位字序列（去掉每字前的 00）: 
    03?? 0020 0001 6000 ... 
  正确读法 A: size = be16(+2..+3) 即 (b2<<8)|b3 ; addr = be16(+4..+5) 即 (b4<<8)|b5 ; flags=be16(+6..+7)
      item0: size=(00<<8)|0x20=0x20  <- 仍太小
  正确读法 B: 字节对 (b1,b2),(b3,b4),(b5,b6) 视作 be16 = 0x0020,0x0000,0x0160
  ......
下面用纯机器方法判：找出唯一使 sum(size)==161628 且无重叠 的线性字段抽取。
"""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW); T = 0x1164
RAW = [FW[T+i*8:T+i*8+8] for i in range(12)]

print("=" * 84)
print("A5. 定案搜索：把 96 B 表当成 48 个 u16（两种端序）流，寻找 (size,addr) 字段位置")
print("=" * 84)

def u16s(endian):
    return [int.from_bytes(FW[T+2*k:T+2*k+2], endian) for k in range(48)]

for endian in ("big", "little"):
    w = u16s(endian)
    print(f"\n--- 端序 {endian} 的 48 个 u16 字 ---")
    for r in range(12):
        print(f"  item{r:2d}: " + " ".join(f"{w[r*4+c]:04x}" for c in range(4)))

print("\n" + "=" * 84)
print("判据搜索：字段必须是 4 个 u16(每项) 中的某 2 个，一个当 size(0x1000倍数)，一个当 addr")
print("=" * 84)
U16 = {}
for endian in ("big", "little"):
    w = u16s(endian)
    for szk in range(4):
        for adk in range(4):
            if szk == adk: continue
            szf = [w[r*4+szk] for r in range(12)]
            adf = [w[r*4+adk] for r in range(12)]
            if not all(s % 0x1000 == 0 and s > 0 for s in szf): continue
            segs = sorted(zip(adf, szf))
            ov = sum(1 for i in range(1,12) if segs[i][0] < segs[i-1][0]+segs[i-1][1])
            cov = sum(szf)
            hi = max(a+s for a,s in segs)
            if ov == 0 and cov in (N, 0x18000) or (ov==0 and hi <= N+0x1000):
                print(f"  endian={endian} sizeU16#{szk} addrU16#{adk} "
                      f"cov={cov}(0x{cov:X}) 重叠={ov} hi=0x{hi:X}")
                print(f"     size={[hex(s) for s in szf]}")
                print(f"     addr={[hex(a) for a in adf]}")

print("\n" + "=" * 84)
print("★ 关键洞察：4 个字/项 -> 检测共有的模式")
print("   item: [w0][w1][w2][w3]，实测(big) w0=0x0300/0x0200, w1={0x20,0x30,0x10}*0x100,")
print("         w2={0x0..0x1}*0x10000+{0x60..}, w3=0")
print("=" * 84)
wb = u16s("big"); wl = u16s("little")
print(f"{'#':>3} {'w0':>6} {'w1':>6} {'w2':>6} {'w3':>6} | {'l0':>6} {'l1':>6} {'l2':>6} {'l3':>6}")
for r in range(12):
    print(f"{r:>3} " + " ".join(f"{wb[r*4+c]:04x}" for c in range(4)) + " | " +
          " ".join(f"{wl[r*4+c]:04x}" for c in range(4)))

print("\n>>> 结论：w1(big) = size，w2(big) = addr，w0(big) 高字节 = type")
print("    即: type = FW[o+0], pad=FW[o+1], size = be16@(o+2), addr = be16@(o+4), flags=be16@(o+6)")
items=[]
for i in range(12):
    o=T+i*8
    t=FW[o]; sz=be16(FW,o+2); ad=be16(FW,o+4); fl=be16(FW,o+6)
    items.append((i,t,sz,ad,fl))
for i,t,sz,ad,fl in items:
    print(f"  [{i:2d}] type=0x{t:02X} size={sz:>6d}(0x{sz:04X}) addr=0x{ad:04X} flags=0x{fl:04X} "
          f"[0x{ad:05X},0x{ad+sz:05X})")
print(f"\n  size总和={sum(s for _,_,s,_,_ in items)} = 0x{sum(s for _,_,s,_,_ in items):X}   文件长={N}=0x{N:X}")
print(f"  addr 0x1000对齐: {sum(1 for _,_,_,a,_ in items if a%0x1000==0)}/12")
print(f"  size 0x1000倍数: {sum(1 for _,_,s,_,_ in items if s%0x1000==0)}/12")
segs=sorted((a,s) for _,_,s,a,_ in items)
ov=sum(1 for i in range(1,12) if segs[i][0]<segs[i-1][0]+segs[i-1][1])
print(f"  重叠对: {ov}/11")
lo=min(a for a,_ in segs); hi=max(a+s for a,s in segs)
print(f"  覆盖区间 [0x{lo:X},0x{hi:X})  跨度={hi-lo}  有效字节={sum(s for _,s in segs)}")
print(f"  文件长-跨度 = {N-(hi-lo)}   覆盖率={sum(s for _,s in segs)/(hi-lo)*100:.1f}%")
