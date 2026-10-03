import re,statistics as st
pat=re.compile(r"data=\s*((?:[0-9A-F]{2}\s*){40})")
rows=[]
for ln in open("press-log.txt",encoding="utf-8",errors="ignore"):
    m=pat.search(ln)
    if not m: continue
    b=[int(x,16) for x in m.group(1).split()]
    if len(b)==40:
        rows.append((b[6]|(b[7]<<8), b[39]&1, b[2]|(b[3]<<8), b[4]|(b[5]<<8)))
print("总样本", len(rows))
# 找 0->1 翻转索引
flips=[i for i in range(1,len(rows)) if rows[i][1]==1 and rows[i-1][1]==0]
print("0->1 翻转次数:", len(flips), "位置:", flips)
print()
print("=== 每次翻转前后 ±14 帧的压力序列（★ 看 140 之前有没有振荡）===")
for k,fi in enumerate(flips):
    lo=max(0,fi-14); hi=min(len(rows),fi+8)
    seq=[rows[i][0] for i in range(lo,hi)]
    mark="".join("^" if i==fi else " " for i in range(lo,hi))
    print(f"  事件{k+1} @idx{fi}: {seq}")
    print(f"                {mark}")
print()
print("=== 全序列里，压力在 100..139（未点击）区间时的相邻帧差分 ===")
diffs=[]
for i in range(1,len(rows)):
    if rows[i][1]==0 and 100<=rows[i][0]<=139:
        diffs.append(abs(rows[i][0]-rows[i-1][0]))
if diffs:
    print(f"  n={len(diffs)}  平均|Δ|={st.mean(diffs):.2f}  中位={st.median(diffs)}  最大={max(diffs)}")
    big=[d for d in diffs if d>=10]
    print(f"  |Δ|>=10 的比例: {len(big)}/{len(diffs)} = {100*len(big)/len(diffs):.1f}%")
print()
print("=== 压力>0 且按下位=0 的样本里，压力的分布（看有没有稳定的中间平台）===")
mid=[r[0] for r in rows if r[1]==0 and r[0]>0]
if mid:
    print(f"  n={len(mid)}  最小={min(mid)} 中位={st.median(mid)} 最大={max(mid)}")
    import collections
    c=collections.Counter(mid)
    print("  出现最多的 12 个值:", c.most_common(12))
