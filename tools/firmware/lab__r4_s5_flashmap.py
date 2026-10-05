# -*- coding: utf-8 -*-
"""R4-5: 按官方子固件表把载荷 A 还原成 GT7868Q 的 flash 镜像 + 代码/数据判定（带正对照）"""
import numpy as np, collections, math

A = np.frombuffer(open('A_2024.bin','rb').read(), dtype=np.uint8)   # 子固件数据（表序）
O = open('orig_TB14P.bin','rb').read()
TF = np.frombuffer(O[0x19A3C:0x2775C], dtype=np.uint8)               # 载荷B = TF100A 固件（真 ARM 代码，正对照）

# 官方子固件表（从文件 0x113C+32 直接读出的 13 项）
TBL = [(0x01,2048,0x0FF00),(0x03,8192,0x16000),(0x03,8192,0x06000),(0x03,8192,0x08000),
       (0x03,8192,0x0A000),(0x03,8192,0x0C000),(0x03,8192,0x1E000),(0x03,8192,0x10000),
       (0x02,12288,0x01000),(0x02,4096,0x00000),(0x03,8192,0x04000),(0x02,12288,0x13000),
       (0x02,4096,0x12000)]

def ent(x):
    c = collections.Counter(np.asarray(x).tolist()); t = len(x)
    return -sum((v/t)*math.log2(v/t) for v in c.values())

print("="*94)
print("### 载荷 A 按官方子固件表还原 = GT7868Q flash 镜像")
print("="*94)
print(f"{'idx':>3} {'type':>4} {'flash':>8} {'size':>6} {'载荷A偏移':>10} {'零%':>6} {'熵H':>6} "
      f"{'top1':>6} {'8051@0':>8} {'判定':>8}")
off = 0
blocks = []
for i,(ty,ln,ad) in enumerate(TBL):
    blk = A[off:off+ln]
    blocks.append((i,ty,ad,blk))
    z = 100*(blk==0).mean()
    e = ent(blk)
    c = collections.Counter(blk.tolist())
    top = 100*c.most_common(1)[0][1]/ln
    b0 = blk[0] if len(blk) else 0
    tag = "代码?" if (e<7.0 and z<5) else ("空/稀疏" if z>40 else "数据")
    print(f"{i:>3} {ty:#06x} {ad:#08x} {ln:>6} {off:#10x} {z:>6.2f} {e:>6.3f} "
          f"{top:>5.2f}% {b0:#08x} {tag:>8}")
    off += ln

print("\n" + "="*94)
print("### 正对照：载荷 B = TF100A 固件（已知 Cortex-M3 ARM Thumb 代码）")
print("="*94)
print(f"  长度 {len(TF)}  零% {100*(TF==0).mean():.2f}  熵 {ent(TF):.3f}  "
      f"top1 {100*collections.Counter(TF.tolist()).most_common(1)[0][1]/len(TF):.2f}%")
print(f"  前 64 字节: {' '.join(f'{b:02x}' for b in TF[:64])}")
print(f"  ascii: {''.join(chr(c) if 32<=c<127 else '.' for c in TF[:64])}")

print("\n" + "="*94)
print("### flash 0x00000 与 0x01000 的首部（= 8051 复位向量的位置）")
print("="*94)
for i,ty,ad,blk in blocks:
    if ad in (0x00000, 0x01000):
        print(f"\n  --- flash {ad:#07x} (type {ty:#04x}, {len(blk)} B) 前 96 字节 ---")
        for k in range(0, 96, 16):
            print(f"    +{k:04x}  " + " ".join(f"{b:02x}" for b in blk[k:k+16]))

print("\n" + "="*94)
print("### 8051 判据（带对照）：块首是否 02 xx xx (LJMP) / 12 xx xx (LCALL)")
print("     统计整个块内 02/12 后 16 位目标的高频集中度 —— 真代码会集中在合法地址")
print("="*94)
def opcode_conc(x, op):
    c = collections.Counter()
    for j in range(len(x)-2):
        if x[j] == op:
            c[(int(x[j+1])<<8)|int(x[j+2])] += 1
    n = len(x)
    return len(c), (c.most_common(1)[0][1] if c else 0)
def n_zeros(x, w):
    z = (x==0).astype(np.int8); best=cur=0
    for v in z:
        cur = cur+1 if v else 0
        best = max(best, cur)
    return best

print(f"{'样本':<28} {'02数':>7} {'不同目标':>8} {'最高':>5} | {'12数':>7} {'不同目标':>8} {'最高':>5} | 最长0段")
for name, x in [("载荷A idx9 (flash 0x00000)", blocks[9][3]),
                ("载荷A idx8 (flash 0x01000)", blocks[8][3]),
                ("载荷A idx6 (flash 0x1E000)", blocks[6][3]),
                ("对照:TF100A 载荷B (真ARM码)", TF),
                ("对照:打乱后的载荷A", np.random.default_rng(0).permutation(A[:12288])),
                ("对照:纯随机", np.random.default_rng(1).integers(0,256,12288).astype(np.uint8))]:
    a = opcode_conc(x, 0x02); b = opcode_conc(x, 0x12)
    print(f"{name:<28} {sum(1 for j in range(len(x)-2) if x[j]==0x02):>7} {a[0]:>8} {a[1]:>5} | "
          f"{sum(1 for j in range(len(x)-2) if x[j]==0x12):>7} {b[0]:>8} {b[1]:>5} | {n_zeros(x,0):>6}")

print("\n" + "="*94)
print("### 关键常量搜索（真固件里应当出现自己会用到的地址）")
print("="*94)
def find32(x, val, name):
    le = val.to_bytes(4,'little'); be = val.to_bytes(4,'big')
    hit_le = [hex(i) for i in range(len(x)-3) if bytes(x[i:i+4])==le]
    hit_be = [hex(i) for i in range(len(x)-3) if bytes(x[i:i+4])==be]
    print(f"  {name:<22} LE命中 {len(hit_le):>3} {hit_le[:6]}   BE命中 {len(hit_be):>3} {hit_be[:6]}")
for val, nm in [(0x08000000,"Flash基址(ARM)"),(0x20000000,"SRAM基址(ARM)"),(0x40000000,"外设基址(ARM)"),
                (0x00005000,"TF100A加载基址"),(0x00004160,"CMD_ADDR"),(0x000096F8,"CFG_START(xdata)"),
                (0x00019000,"CFG_FLASH"),(0x5A5A5A5A,"0x5A"),(0x0000002C,"0x2C")]:
    find32(A, val, nm)

print("\n" + "="*94)
print("### 载荷A 里 0x5A(AW86927 I2C地址) / 0x4160 / 0x19000 的单字节出现率")
print("="*94)
for v in (0x5A, 0x5B, 0x2C):
    print(f"  0x{v:02x}: {int((A==v).sum())} 次 ({100*(A==v).mean():.3f}%)  均匀期望 {len(A)/256:.0f}")
