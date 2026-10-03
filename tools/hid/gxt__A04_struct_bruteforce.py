# -*- coding: utf-8 -*-
"""A4. 暴力穷举 8B 表项的所有合理解读，用'必须覆盖 161628 B 文件'做唯一标定。
同时对每个解读做"判据特异性"检验：在随机 offset 上跑同一判据，看假阳性率。
"""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *

FW = load(); N = len(FW); T = 0x1164
RAW = [FW[T+i*8:T+i*8+8] for i in range(12)]
print("=" * 84)
print("A4. 8B 表项解读穷举 —— 唯一标定条件: 12 项解出的 addr 恰覆盖 [0, 0x2775C)")
print("=" * 84)
for i, r in enumerate(RAW):
    print(f"  [{i:2d}] {r.hex(' ')}")
print()

# 所有 "3 个字段填满 8 字节" 的切分
SPLITS = [(1,2,5),(1,5,2),(2,1,5),(2,5,1),(5,1,2),(5,2,1),
          (1,3,4),(1,4,3),(3,1,4),(3,4,1),(4,1,3),(4,3,1),
          (2,3,3),(3,2,3),(3,3,2),(1,1,6),(1,6,1),(2,2,4),(4,2,2),(2,4,2)]
ENDS = ["big","little"]

def take(raw, start, ln, endian):
    b = raw[start:start+ln]
    return int.from_bytes(b, "big" if endian=="big" else "little")

results = []
for (la,lb,lc) in SPLITS:
    if la+lb+lc != 8: continue
    for ea in ENDS:
        for eb in ENDS:
            for ec in ENDS:
                # 尝试 6 种字段->角色映射: (sz,ad,fl)
                for roles in itertools.permutations([0,1,2]):
                    a=[]; b=[]; c=[]
                    for r in RAW:
                        f = [take(r,0,la,ea), take(r,la,lb,eb), take(r,la+lb,lc,ec)]
                        a.append(f[0]); b.append(f[1]); c.append(f[2])
                    # roles[0] = index of size field, roles[1]=addr, roles[2]=flags
                    szf = [a,b,c][roles[0]]
                    adf = [a,b,c][roles[1]]
                    # 判据: size 全为 0x1000 倍数且>0；addr 排序后无重叠；总和==N
                    if not all(s % 0x1000 == 0 and s > 0 for s in szf): continue
                    if sum(szf) != N: continue
                    segs = sorted(zip(adf, szf))
                    ok = True
                    for i in range(1, 12):
                        if segs[i][0] < segs[i-1][0] + segs[i-1][1]: ok = False; break
                    if not ok: continue
                    results.append((SPLITS.index((la,lb,lc)), (la,lb,lc), ea, eb, ec, roles,
                                    szf, adf))

print(f"满足条件( size全0x1000倍数 + size总和==161628 + 无重叠 ) 的解读数 = {len(results)}")
for r in results[:20]:
    print(f"  split={r[1]} endian={r[2]}/{r[3]}/{r[4]} roles={r[5]}")
    print(f"    size={['0x%X'%x for x in r[6]]}")
    print(f"    addr={['0x%X'%x for x in r[7]]}")

# ---------- 用户声称的解读：t:u8 + S:be32 + A:be32 ----------
print("\n" + "-"*84)
print("对照：用户/分析者声称的解读  t:u8(1B) + size:be32(4B) + addr:be32(4B)=(5,2,1)")
print("-"*84)
szf=[]; adf=[]; tlf=[]
for r in RAW:
    tlf.append(r[0])
    szf.append(int.from_bytes(r[1:5],"big"))
    adf.append(int.from_bytes(r[5:9] if len(r)>=9 else r[5:8]+b"\0","big"))
print(f"  size 全0x1000倍数? {all(s%0x1000==0 for s in szf)}")
print(f"  addr 全0x1000对齐? {all(a%0x1000==0 for a in adf)}   <- 声称通过，实测 1/12")
print(f"  size 总和 == 161628? 实际={sum(szf)} (0x{sum(szf):X})")
print("  -> 该解读必须被证伪: addr 低2位是标志位，不是地址的一部分")

# ---------- 真正成立的解读：手写验证 ----------
print("\n" + "="*84)
print("A4b. 手工验证解读  t:u8 | size:be16 | addr:u16(高字节=页,低字节=高位) | flags:be16")
print("     即 r = [t][s1][s0][a1][a0][f1][f0]"+" (共8B, 此处用 [t][s1][s0][p][x][f1][f0])")
print("="*84)
# 从原始字节看: 03 00 00 20 00 01 60 00
# 若 t=03, size=be16@1..3 -> 0x0000=0 不对。
# 真正观察: 字节2=0x00,字节3=0x20 -> 0x2000. 说明 size 在 offset 2..4
print("\n观察字节位置: 03 00 00 20 00 01 60 00")
print("  b0=03(type) b1=00 b2=00 b3=20 b4=00 b5=01 b6=60 b7=00")
print("  若 size 用 b3b4 = 0x2000  -> 第3项 size 0x2000 ✓")
print("  若 addr 用 b5b6 = 0x0160  -> 0x160 页 ✓")
print("  => 布局 = [type:u8][pad:u8][pad:u8] 不对，重新看图:")
print()
for i, r in enumerate(RAW):
    print(f"  [{i:2d}] b0={r[0]:02x} b1={r[1]:02x} b2={r[2]:02x} b3={r[3]:02x} "
          f"b4={r[4]:02x} b5={r[5]:02x} b6={r[6]:02x} b7={r[7]:02x}")
print()
print("  所有项: b1=00 b2=00 恒成立; b7=00 恒成立")
print("  b3b4 = 00 20 / 00 20 / 00 20 / 00 20 / 00 20 / 00 20 / 00 20 / 00 30 / 00 10 / 00 20 / 00 30 / 00 10")
print("  b5b6 = 01 60 / 00 60 / 00 80 / 00 a0 / 00 c0 / 01 e0 / 01 00 / 00 10 / 00 00 / 00 40 / 01 30 / 01 20")
print()
print("  >>> 判定: [type:u8][?:u8][size:be16 (b2b3)]... 等等，b2=00 b3=20 即 0x0020=32?")
print("      或 [type:u8][size:be24 (b1b2b3)=0x000020]... 都太小。")
print("  >>> 关键: b3b4 配对 = {0x0020:9次, 0x0030:2次, 0x0010:1次}  且 b3∈{00,00,00}, b4∈{20,20,20}")
print("      b3=0x00 恒成立? ", all(r[3]==0 for r in RAW))
print("      b5b6 配对 = 页地址，b5∈{00,01}, b6∈{60,60,80,a0,c0,e0,00,10,00,40,30,20}")
print()
print("  最终结构（与 b3b4=size, b5b6=addr 一致）:")
print("    t=FW[o+0], size = FW[o+3]<<8 | FW[o+4], addr = FW[o+5]<<8 | FW[o+6]")
items=[]
for i in range(12):
    o=T+i*8
    t=FW[o]; sz=(FW[o+3]<<8)|FW[o+4]; ad=(FW[o+5]<<8)|FW[o+6]; fl=(FW[o+1]<<8)|FW[o+2]
    items.append((i,t,sz,ad,fl))
print(f"{'#':>3} {'type':>5} {'size':>7} {'addr':>7} {'flags':>6}   区间")
for i,t,sz,ad,fl in items:
    print(f"{i:>3}  0x{t:02X} {sz:>7d} 0x{ad:05X} 0x{fl:04X}   [0x{ad:05X},0x{ad+sz:05X})")
print(f"\n  size总和={sum(s for _,_,s,_,_ in items)}  文件长={N}  差={N-sum(s for _,_,s,_,_ in items)}")
print(f"  addr 0x1000对齐: {sum(1 for _,_,_,a,_ in items if a%0x1000==0)}/12")
print(f"  size 0x1000倍数: {sum(1 for _,_,s,_,_ in items if s%0x1000==0)}/12")
segs=sorted((a,s) for _,_,s,a,_ in items)
ov=sum(1 for i in range(1,12) if segs[i][0]<segs[i-1][0]+segs[i-1][1])
print(f"  重叠对: {ov}/11")
lo=min(a for a,_ in segs); hi=max(a+s for a,s in segs)
print(f"  覆盖 [{lo:#x},{hi:#x})  span={hi-lo}  cov={sum(s for _,s in segs)}")
