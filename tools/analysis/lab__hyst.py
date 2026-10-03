import re,statistics as st
pat=re.compile(r"data=\s*((?:[0-9A-F]{2}\s*){40})")
rows=[]
for ln in open("press-log.txt",encoding="utf-8",errors="ignore"):
    m=pat.search(ln)
    if not m: continue
    b=[int(x,16) for x in m.group(1).split()]
    if len(b)==40:
        rows.append({"p":b[6]|(b[7]<<8),"btn":b[39]&1,"b1":b[1]&0x0f,"b38":b[38],"b39":b[39]})
print("样本",len(rows))
dn=[(i,rows[i]["p"]) for i in range(1,len(rows)) if rows[i]["btn"]==1 and rows[i-1]["btn"]==0]
up=[(i,rows[i]["p"]) for i in range(1,len(rows)) if rows[i]["btn"]==0 and rows[i-1]["btn"]==1]
print("按下沿 n=%d 压力=%s"%(len(dn),[v for _,v in dn]))
print("抬起沿 n=%d 压力=%s"%(len(up),[v for _,v in up]))
print()
print("=== 抬起沿前后的压力序列（看滞回）===")
for k,(fi,v) in enumerate(up):
    lo=max(0,fi-10); hi=min(len(rows),fi+4)
    seq=[rows[i]["p"] for i in range(lo,hi)]
    print(f"  抬起{k+1} @idx{fi}: {seq}   (抬起瞬间={v})")
print()
print("=== byte38 / byte1 低4位 与 btn 的关系 ===")
from collections import Counter
print("  byte38 取值:",Counter(r["b38"] for r in rows).most_common())
print("  byte39 取值:",Counter(r["b39"] for r in rows).most_common())
print("  (btn=1 时 byte38):",Counter(r["b38"] for r in rows if r["btn"]==1).most_common())
print("  (btn=0 时 byte38):",Counter(r["b38"] for r in rows if r["btn"]==0).most_common())
print("  (btn=1 时 byte1&0xf):",Counter(r["b1"] for r in rows if r["btn"]==1).most_common())
print("  (btn=0 时 byte1&0xf):",Counter(r["b1"] for r in rows if r["btn"]==0).most_common())
# 滞回带内压力分布
band=[r["p"] for r in rows if 98<r["p"]<140]
print()
print(f"=== 滞回带 (98,140) 内样本: n={len(band)}  按下态/抬起态混合 ===")
if band:
    hi_p=[r["p"] for r in rows if 98<r["p"]<140 and r["btn"]==1]
    lo_p=[r["p"] for r in rows if 98<r["p"]<140 and r["btn"]==0]
    print(f"    btn=1 的: n={len(hi_p)} 范围={min(hi_p) if hi_p else '-'}..{max(hi_p) if hi_p else '-'}")
    print(f"    btn=0 的: n={len(lo_p)} 范围={min(lo_p) if lo_p else '-'}..{max(lo_p) if lo_p else '-'}")
