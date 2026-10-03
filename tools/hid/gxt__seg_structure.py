# -*- coding: utf-8 -*-
"""
实验 D：最后一击 —— 确定加扰段的真实结构。

已知：
  - T（1024B）是完美平衡的纯随机表：256 值各出现 4 次，无任何周期。
  - "mod 1024 众数占比 9.7%" 的信号是真的且强（25x 基线）。
  - 但众数值≠T[ph]，也≠T[ph]^FF ⇒ 不是简单的 C = P XOR T。
  - 众数值有规律：0x34,0x36,0x3C,0x3E,0x10,0x12,0x18,0x1A（低4位全偶）

假设 D1：加扰段本身就是"结构化的"——它可能是一个 **地址表/波形表**，
        每个"相位"实际对应一个字段，字段值域天然很窄。
假设 D2：所谓 1024 周期其实是"**每 1024 字节一个记录**"的结构，
        而非加扰周期。即固件是 [1024B 记录] × N。
假设 D3：加扰 = 字节置换 + 位操作，不是 XOR。

本轮：直接把加扰段按 1024 切块，看成 N×1024 矩阵，看列/行的统计。
"""
import os, collections, math, struct

HERE = os.path.dirname(os.path.abspath(__file__))
FW = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
fw = open(FW,'rb').read()
yi = fw.find(b'YELSTO')
seg = fw[yi:]

L=[]
def w(s=''): L.append(s); print(s)

w('='*80); w('实验 D：加扰段的真实结构'); w('='*80)
w('加扰段起始 0x%04X，长度 %d B' % (yi, len(seg)))
w('长度 / 1024 = %.3f  →  完整 1024B 块 %d 个，余 %d B'
  % (len(seg)/1024, len(seg)//1024, len(seg)%1024))

# ---- D1: 1024 列的列统计 ----
w(); w('### D1. 按 1024 分列后，每列的字节分布（只看前 32 列）')
w('```')
cols = collections.defaultdict(list)
for k,x in enumerate(seg): cols[k%1024].append(x)
w(' 列号 | 样本数 | 众数 | 占比 | 次众数 | 占比 | 不同值数')
for ph in list(range(0,32))+[64,128,192,256,320,512,768,1023]:
    g = cols[ph]; cc = collections.Counter(g); mc = cc.most_common(2)
    w(' %5d | %6d | 0x%02X | %.4f | 0x%02X | %.4f | %d'
      % (ph, len(g), mc[0][0], mc[0][1]/len(g),
         mc[1][0] if len(mc)>1 else 0, mc[1][1]/len(g) if len(mc)>1 else 0,
         len(cc)))
w('```')

# ---- D2: 看前 1024 B 原始 hex（第一块） ----
w(); w('### D2. 加扰段第一块 1024 B 原样 hexdump（每行 32 B，前 512 B）')
w('```')
for k in range(0, 512, 32):
    ch = seg[k:k+32]
    w('%04X  %-95s |%s|' % (k, ch.hex(' '), ''.join(chr(c) if 32<=c<127 else '.' for c in ch)))
w('```')

# ---- D3: 块间相似度 —— 第 0 块 vs 第 n 块 ----
w(); w('### D3. 块间逐字节相等率（第 0 块 vs 第 n 块，1024 B 对齐）')
w('```')
B0 = seg[:1024]
for n in [1,2,3,4,5,8,16,32,64,100]:
    off = n*1024
    if off+1024 > len(seg): break
    Bn = seg[off:off+1024]
    eq = sum(1 for i in range(1024) if B0[i]==Bn[i])/1024
    w(' 块 %3d（偏移 0x%05X）：相等率 %.4f（基线 %.4f，×%.1f）'
      % (n, off, eq, 1/256, eq/(1/256)))
w('```')

# ---- D4: 块内自相似：把 1024 B 块再按 32/64 看 ----
w(); w('### D4. 块内 32 B 行之间的差分模式（第 0 块前 8 行）')
w('```')
rows = [seg[i*32:(i+1)*32] for i in range(32)]
for i in range(8):
    w(' 行%d: %s' % (i, rows[i].hex(' ')))
w(' 行间逐字节差(行0 vs 行1, 模256):')
d = [(rows[1][i]-rows[0][i])%256 for i in range(32)]
w('   ' + ' '.join('%02X'%x for x in d))
w(' 行间逐字节差(行2 vs 行0):')
d = [(rows[2][i]-rows[0][i])%256 for i in range(32)]
w('   ' + ' '.join('%02X'%x for x in d))
w('```')

# ---- D5: 直方图：加扰段整体 vs 真随机 ----
w(); w('### D5. 加扰段字节直方图 vs 随机（卡方）')
w('```')
c = collections.Counter(seg); n = len(seg); exp = n/256
chi = sum((c.get(v,0)-exp)**2/exp for v in range(256))
w(' 卡方 = %.1f（自由度 255，随机期望 ≈255，p=0.05 临界 293）' % chi)
w(' 最高频 8 个：' + ' '.join('0x%02X:%d'%(v,k) for v,k in c.most_common(8)))
w(' 最低频 8 个：' + ' '.join('0x%02X:%d'%(v,k) for v,k in c.most_common()[-8:]))
w('```')

text='\n'.join(L)
open(os.path.join(HERE,'cfg_parsed','seg_structure.txt'),'w',encoding='utf-8').write(text)
w(); w('写入 cfg_parsed/seg_structure.txt')
