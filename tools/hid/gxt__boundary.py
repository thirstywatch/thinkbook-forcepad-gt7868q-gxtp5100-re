# -*- coding: utf-8 -*-
"""
实验 E：定位加扰边界 + 判决。

D2 显示 YELSTO(0x1142) 之后约 232 B 仍是明文，之后变噪声。
本轮精确定位边界，并对"噪声区"重跑判据。
"""
import os, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
FW = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
fw = open(FW,'rb').read()
yi = fw.find(b'YELSTO')
seg = fw[yi:]

L=[]
def w(s=''): L.append(s); print(s)

def entropy(b):
    if not b: return 0.0
    c=collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

w('='*80); w('实验 E：精确定位明文/噪声边界'); w('='*80)
w('YELSTO 固件偏移 = 0x%04X' % yi)

# 逐 32 B 窗口熵，找突变点
w(); w('### E1. 从 YELSTO 起逐 32B 窗口熵（找突变）')
w('```')
prev=None
for k in range(0, 4096, 32):
    ch = seg[k:k+32]
    h = entropy(ch)
    z = ch.count(0)/len(ch)
    mark=''
    if prev is not None and h-prev > 2.5: mark=' ★熵突增'
    w(' +0x%04X (固件 0x%04X)  H=%.3f  0占比=%.2f%s' % (k, yi+k, h, z, mark))
    prev=h
w('```')

# 用 64B 滑动找第一个连续高熵区
w(); w('### E2. 用 256B 窗口找第一个 H>7.5 的起点')
w('```')
first=None
for k in range(0, 8192, 16):
    if k+256>len(seg): break
    if entropy(seg[k:k+256])>7.5:
        first=k; break
w(' 第一个 H>7.5 的 256B 窗口起点：+0x%04X（固件 0x%04X）' % (first, yi+first))
w('```')

# 噪声区重跑：从 first 开始
w(); w('### E3. 噪声区（从 +0x%04X 起）的 mod-1024 列统计' % first)
noise = seg[first:]
cols=collections.defaultdict(list)
for k,x in enumerate(noise): cols[k%1024].append(x)
shares=[]
for ph in range(1024):
    g=cols[ph]
    if len(g)<8: continue
    shares.append(collections.Counter(g).most_common(1)[0][1]/len(g))
shares.sort()
w('```')
w(' 组数 %d，众数占比 中位 %.4f 均值 %.4f max %.4f（随机基线 %.4f）'
  % (len(shares), shares[len(shares)//2], sum(shares)/len(shares), shares[-1], 1/256))
w(' 提升倍数（中位）：×%.1f' % (shares[len(shares)//2]/(1/256)))
w('```')

# 噪声区卡方
w(); w('### E4. 噪声区直方图')
w('```')
c=collections.Counter(noise); n=len(noise); exp=n/256
chi=sum((c.get(v,0)-exp)**2/exp for v in range(256))
w(' 长度 %d，卡方 %.1f（随机期望 255，p=0.05 临界 293）' % (n, chi))
w(' 最高频：' + ' '.join('0x%02X:%d'%(v,k) for v,k in c.most_common(8)))
w('```')

text='\n'.join(L)
open(os.path.join(HERE,'cfg_parsed','boundary.txt'),'w',encoding='utf-8').write(text)
w(); w('写入 cfg_parsed/boundary.txt')
