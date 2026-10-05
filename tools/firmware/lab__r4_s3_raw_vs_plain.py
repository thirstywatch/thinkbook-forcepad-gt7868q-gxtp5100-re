# -*- coding: utf-8 -*-
"""R4-3: raw（原始） vs plain（上一轮"解扰"产物）结构对照 —— 谁才是结构化数据？"""
import numpy as np, collections

O = open('orig_TB14P.bin', 'rb').read()
A = np.frombuffer(open('A_2024.bin', 'rb').read(), dtype=np.uint8)
K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
R0 = 0x113C
SZ = 100602
RAW = np.frombuffer(O[R0+256:R0+SZ+6], dtype=np.uint8)   # 100352 B 原始子固件数据
assert len(RAW) == len(A) == 100352

def metrics(x, name):
    n = len(x)
    h = collections.Counter(x.tolist())
    ent = -sum((c/n)*np.log2(c/n) for c in h.values())
    top = h.most_common(1)[0]
    # 4 字节全零段，绝对偏移 mod 8
    z = (x == 0).astype(np.uint8)
    runs = []
    i = 0
    while i < n:
        if z[i]:
            j = i
            while j < n and z[j]: j += 1
            if j - i >= 4: runs.append(i)
            i = j
        else: i += 1
    al = sum(1 for s in runs if s % 8 == 4)
    # 每 16 字节记录的 4 个位置的高频值集中度
    conc = []
    for p in range(4):
        col = x[p::4]
        c = collections.Counter(col.tolist())
        conc.append(c.most_common(5))
    print(f"\n--- {name} ---")
    print(f"  len={n}  熵 H={ent:.3f} bit/byte   零%={100*(x==0).mean():.2f}")
    print(f"  最高频字节: 0x{top[0]:02x} 占 {100*top[1]/n:.2f}%   (均匀基线 0.39%)")
    print(f"  ≥4 字节全零段数={len(runs)}  其中绝对偏移 mod8==4 的={al} ({100*al/max(1,len(runs)):.1f}%)")
    print(f"  位置 p=0..3 的最高频值: " +
          " | ".join(" ".join(f"{v:02x}:{100*c/n*4:.1f}%" for v,c in m[:3]) for m in conc))
    print(f"  u32 相邻自相关 rho(1) = {np.corrcoef(x[:-4].astype(float), x[4:].astype(float))[0,1]:+.4f}")
    return ent

print("="*78)
metrics(RAW, "RAW  （原始文件里的子固件数据）")
metrics(A,   "PLAIN（上一轮 raw XOR K[off%1024] 的产物）")

print("\n" + "="*78)
print("### K 的位结构体检")
Kc = K
for p in range(4):
    col = Kc[p::4]
    used = 0
    for b in range(8):
        if (col >> b & 1).any(): used |= (1 << b)
    print(f"  K 中 p%4={p} 的列: 用到的位 = " +
          ",".join(str(b) for b in range(8) if used>>b & 1) + f"   （共 {bin(used).count('1')}/8）")
print("  K 是否 16 位周期 =", np.array_equal(K[:512], K[512:]))
print("  K 的 256 个值是否各出现 4 次 =",
      sorted(collections.Counter(K.tolist()).values()) == [4]*256)
print("  K 的零值位置 =", [i for i in range(1024) if K[i] == 0])

print("\n" + "="*78)
print("### 原始数据里 K[off%1024] 的“零区”（= 上一轮认为的 'plain 的零填充'）")
base = R0 + 256
zero_pos = []
for j in range(len(RAW)):
    if RAW[j] == K[(base + j) % 1024]:
        zero_pos.append(j)
zp = np.array(zero_pos)
print(f"  命中位置数 = {len(zp)} ({100*len(zp)/len(RAW):.2f}%)")
if len(zp):
    # 连续段
    segs = []
    s = zp[0]; p = zp[0]
    for v in zp[1:]:
        if v == p + 1: p = v
        else: segs.append((s, p)); s = v; p = v
    segs.append((s, p))
    segs = [(a,b) for a,b in segs if b-a+1 >= 4]
    print(f"  ≥4 的连续段 {len(segs)} 个，最长 5 个：")
    for a, b in sorted(segs, key=lambda t: -(t[1]-t[0]))[:5]:
        print(f"     子固件内偏移 +{a:#x}..+{b:#x}  (len {b-a+1})   文件绝对 0x{base+a:x}")

print("\n" + "="*78)
print("### raw 前 512 字节（十六进制）")
for i in range(0, 512, 16):
    print(f"  {i:04x}  " + " ".join(f"{b:02x}" for b in RAW[i:i+16]))
print("\n### raw 在 flash 地址维度的第一块（idx0 = ISP @flash 0xFF00, 2048 B）")
for i in range(0, 128, 16):
    print(f"  {i:04x}  " + " ".join(f"{b:02x}" for b in RAW[i:i+16]))
