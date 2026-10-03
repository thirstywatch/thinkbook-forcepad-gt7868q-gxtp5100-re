import re,sys,os
from collections import defaultdict
paths=[p for p in ["press-log-20260913-afterwrite25.txt","press-log.txt"] if os.path.exists(p)]
pat=re.compile(r"data=\s*((?:[0-9A-F]{2}\s*){40})")
for path in paths:
    rows=[]
    for ln in open(path,encoding="utf-8",errors="ignore"):
        m=pat.search(ln)
        if not m: continue
        b=[int(x,16) for x in m.group(1).split()]
        if len(b)==40: rows.append(b)
    if not rows: continue
    print(f"\n===== {path}  ({len(rows)} 条) =====")
    # 按下位 = byte39 & 1
    press=[r[39]&1 for r in rows]
    pres=[r[6]|(r[7]<<8) for r in rows]
    # 找到第一次按下→抬起区间，看区间内压力
    flips=[(i,pres[i]) for i in range(1,len(rows)) if press[i]!=press[i-1]]
    dn=[v for i,v in flips if press[i]==1]
    print(f"  按下位翻转点: 按下 n={len(dn)} 压力={sorted(set(dn))[:12]}")
    if dn:
        lo=min(dn)
        print(f"  最低的按下压力 = {lo}")
        # 只看压力 < lo 的样本，找哪些字节/位发生过变化
        sub=[r for r in rows if (r[6]|(r[7]<<8))<lo]
        print(f"  压力 < {lo} 的样本数 = {len(sub)}")
        if sub:
            for bi in range(40):
                vals=set(r[bi] for r in sub)
                if len(vals)>1:
                    print(f"    byte[{bi}] 在低压区就有 {len(vals)} 种取值: {sorted(vals)[:10]}")
            for bi in range(40):
                bits=defaultdict(int)
                for r in sub: 
                    for k in range(8): bits[(k, (r[bi]>>k)&1)]+=1
                # 找出在低压区既有0又有1的位
                mixed=[k for k in range(8) if bits[(k,0)]>0 and bits[(k,1)]>0]
                if mixed:
                    print(f"    byte[{bi}] 低压区混合位: {mixed}")
