# -*- coding: utf-8 -*-
"""7867 明文固件 vs cfg / 我们的配置体：跨文件逐字节重复搜索（排除平凡片段）"""
import struct, collections, os
FW="<WORKSPACE>"
fw=open(FW,'rb').read()
d=open("bios-re/GT7868Q_native_fw.bin",'rb').read()
BODY=d[0x4C:0x4C+1024]; TAIL=d[0x4C+1024:0x4C+1084]
CFG="<WORKSPACE>"
sid={n:open(CFG+n,'rb').read() for n in ("sid0.bin","sid2.bin","sid3.bin")}
def trivial(b,th=2): return len(set(b))<=th
def common(a,b,minlen=12,top=12):
    """返回 a 中在 b 里出现的 ≥minlen 的最长公共片段（贪心，跳过平凡）"""
    out=[]; i=0
    while i < len(a)-minlen:
        best=(0,-1)
        # 用 b 的 minlen 片段索引加速
        if i==0: 
            idx={}
            for k in range(len(b)-minlen+1):
                idx.setdefault(b[k:k+minlen], k)
            globals()['_idx_%d'%id(b)]=idx
        idx=globals().get('_idx_%d'%id(b), {})
        cand=idx.get(a[i:i+minlen])
        if cand is not None:
            # 向两边扩展（只向右，因为 i 递增）
            L=minlen
            while i+L<len(a) and cand+L<len(b) and a[i+L]==b[cand+L]: L+=1
            seg=a[i:i+L]
            if not trivial(seg): out.append((i,cand,L))
            i+=L
        else:
            i+=1
    out.sort(key=lambda z:-z[2])
    return out[:top]
print("fw = x_108e1f62/tpfw.bin (%d B, GT7867 MARSEI 明文)"%len(fw))
print()
for nm in list(sid)+["我们的配置体","我们的60B尾"]:
    tgt = sid.get(nm, BODY if nm=="我们的配置体" else TAIL)
    # 双向：tgt 的片段是否在 fw 里
    r1=common(tgt, fw, 12)
    r2=common(fw, tgt, 12)
    tot1=sum(L for _,_,L in r1); tot2=sum(L for _,_,L in r2)
    print("### %-12s (%d B)   → 在 fw 中命中 %d 段 / %d B ；fw → 命中 %d 段 / %d B"
          %(nm,len(tgt),len(r1),tot1,len(r2),tot2))
    for off,cand,L in r1[:6]:
        print("     %s+0x%03X == fw+0x%05X  长 %3d : %s"%(nm,off,cand,L,tgt[off:off+min(L,28)].hex(' ')))
    for off,cand,L in r2[:4]:
        print("     fw+0x%05X == %s+0x%03X  长 %3d : %s"%(off,nm,cand,L,fw[off:off+min(L,28)].hex(' ')))
    print()
