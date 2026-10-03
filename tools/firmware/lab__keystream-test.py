import collections,math
p=r"<WORKSPACE>"
b=open(p,"rb").read()
seg=b[0x1000:0x18000]   # 加扰主体
def H(data):
    if not data: return 0
    c=collections.Counter(data); n=len(data)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
print("加扰主体 %d B  整体熵=%.4f"%(len(seg),H(seg)))
print()
print("=== 按候选周期 P 分组，算各类内平均熵（周期对 ⇒ 类内熵低）===")
print("   P     加权平均类内熵   最小类熵  最大类熵")
res=[]
for P in list(range(1,65))+[128,256,300,512,1024]:
    classes=[seg[i::P] for i in range(P)]
    if any(len(c)<8 for c in classes): continue
    hs=[H(c) for c in classes]
    wavg=sum(h*len(c) for h,c in zip(hs,classes))/len(seg)
    res.append((P,wavg,min(hs),max(hs)))
for P,w,mn,mx in res:
    flag="  ← ★ 显著低" if w<7.90 else ""
    print(f"  {P:4d}   {w:.4f}        {mn:.4f}    {mx:.4f}{flag}")
print()
best=sorted(res,key=lambda t:t[1])[:5]
print("类内熵最低的 5 个周期:", [(P,round(w,4)) for P,w,_,_ in best])
print()
print("=== 另一判据：字节异或自相关（对每个 lag 算 x[i]^x[i+lag] 的熵）===")
print("   lag   异或后熵    (低 ⇒ 该 lag 有固定关系)")
for lag in [1,2,3,4,5,6,7,8,12,16,32,64,128,256,512,1024]:
    x=bytes(seg[i]^seg[i+lag] for i in range(len(seg)-lag))
    print(f"  {lag:4d}   {H(x):.4f}")
