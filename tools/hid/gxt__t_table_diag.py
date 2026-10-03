# -*- coding: utf-8 -*-
"""
实验 C：诊断 B1 的强信号（众数占比 0.0974 vs 基线 0.0039）到底是什么。

B1 的信号强到不可能是"明文重复"。一个 1024 周期的表 T 作用在明文上，
只有当"某相位的明文分布高度集中"时，密文才会集中。
但 25 倍的集中度意味着 T 表本身有巨大结构。

第一怀疑：**T 的 1024 B 本身不是随机的**，而是"若干重复模式拼起来的"。
用自相关查 T。
"""
import os, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
FW = r'C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN'
T = open(os.path.join(HERE,'K_gt7868q.bin'),'rb').read()

L=[]
def w(s=''): L.append(s); print(s)

w('='*80); w('实验 C：T 表自身的结构 + B1 信号溯源'); w('='*80)

# ---- C1: T 的自相关（字节相等率）----
w(); w('### C1. T（1024 B）自相关：位移 d 下 T[i]==T[i+d] 的比例'); w('```')
base = 1/256
hits=[]
for d in list(range(1,65))+[128,192,256,320,384,448,512,640,768]:
    n = sum(1 for i in range(len(T)-d) if T[i]==T[i+d])
    r = n/(len(T)-d)
    hits.append((r,d))
    if r > base*2.5:
        w(' 位移 %4d：相等率 %.4f（基线 %.4f，×%.1f）★' % (d, r, base, r/base))
hits.sort(reverse=True)
w(' 前 8 大：' + ' '.join('d=%d(%.4f)'%(d,r) for r,d in hits[:8]))
w('```')

# ---- C2: T 的各种周期假设 ----
w(); w('### C2. T 是否为更短周期的重复'); w('```')
for p in [16,32,64,128,256,512]:
    if len(T)%p: continue
    reps = len(T)//p
    if all(T[i]==T[i%p] for i in range(len(T))):
        w(' 周期 %d：完全重复 ×%d ✅' % (p, reps))
    else:
        match = sum(1 for i in range(len(T)) if T[i]==T[i%p])/len(T)
        w(' 周期 %d：匹配率 %.4f' % (p, match))
w('```')

# ---- C3: T 的字节值分布 ----
w(); w('### C3. T 的字节值分布（看是否被少数值主导）'); w('```')
c = collections.Counter(T)
w(' 不同值 %d，最高频：' % len(c))
for v,n in c.most_common(10):
    w('   0x%02X : %d (%.4f)' % (v,n,n/len(T)))
# 是否成对出现（value^0xFF 也有）
pairs = sum(1 for v in range(256) if c.get(v,0)>0 and c.get(v^0xFF,0)>0)
w(' 值与其补都出现的数量：%d / 256' % pairs)
w('```')

# ---- C4: 关键 —— 明文假设下的众数反推 ----
w(); w('### C4. 直接检验：T 是否等于「某段固件字节 ^ 常量」')
fw = open(FW,'rb').read()
# 如果加扰区 P = C ^ T 且 P 大部分是 0x00 或 0xFF（擦除态）
# 那么 C 在每个相位上应高度集中在 T[i] 或 T[i]^0xFF
seg = fw[fw.find(b'YELSTO'):]
groups = collections.defaultdict(list)
for k,x in enumerate(seg): groups[k%1024].append(x)
w(' 相位 | T[ph] | 组众数 | 众数占比 | 众数==T | 众数==T^0xFF')
agreeT=agreeInv=0; tot=0
for ph in range(0,1024,64):
    g = groups[ph]; cc = collections.Counter(g); mv,mn = cc.most_common(1)[0]
    a = (mv==T[ph]); b = (mv==(T[ph]^0xFF))
    agreeT += a; agreeInv += b; tot += 1
    w('  %4d | 0x%02X | 0x%02X | %.4f | %s | %s' % (ph, T[ph], mv, mn/len(g), a, b))
w(' 汇总（抽样 %d 个相位）：众数==T 的有 %d 个，众数==T^FF 的有 %d 个' % (tot, agreeT, agreeInv))
w('```')

text='\n'.join(L)
open(os.path.join(HERE,'cfg_parsed','t_table_diag.txt'),'w',encoding='utf-8').write(text)
w(); w('写入 cfg_parsed/t_table_diag.txt')
