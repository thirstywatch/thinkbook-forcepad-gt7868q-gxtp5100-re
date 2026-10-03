import os,glob,collections,math,re
def H(d):
    if not d: return 0
    c=collections.Counter(d); n=len(d)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
def analyze(p):
    b=open(p,"rb").read()
    if len(b)<4096: return None
    # 1) 全零段（>=1024）
    zero=0; run=0; maxrun=0
    for x in b:
        if x==0: run+=1; maxrun=max(maxrun,run)
        else: run=0
    # 2) 16字节块重复率（取中段 64KB 避免头部偏置）
    mid=b[len(b)//4:len(b)//4+65536] if len(b)>262144 else b
    blocks=collections.Counter(mid[i:i+16] for i in range(0,len(mid)-15,16))
    tot=sum(blocks.values()); dup=(tot-len(blocks))/max(1,tot)
    # 3) ASCII 路径/工具链串
    strs=re.findall(rb'[\x20-\x7e]{12,}', b)
    paths=[s.decode('latin1') for s in strs if re.search(rb'[A-Za-z]:[\\/]|/usr/|libgcc|riscv|arm-none|gcc|GNU ', s)]
    # 4) 熵
    e=H(b[:0x1000] if len(b)>=0x1000 else b)
    return dict(size=len(b), zeros=maxrun, dup=dup, ent=e, paths=paths[:3], nstr=len(strs))
files=[]
for root in [r"<WORKSPACE>",
             r"<LAB>\touchpad-lab",
             r"<HOME>\Downloads"]:
    for pat in ("**/*.bin","**/*.fw","**/*.cap","**/*.BIN","**/*.img"):
        files+=glob.glob(os.path.join(root,pat),recursive=True)
files=sorted(set(f for f in files if os.path.getsize(f)>20000))
print(f"扫描 {len(files)} 个候选文件\n")
print(f"{'文件':<52}{'大小':>9}{'最长零段':>9}{'块重复':>8}{'头熵':>7}  明文判据")
print("-"*110)
for f in files:
    try: r=analyze(f)
    except Exception as ex: continue
    if not r: continue
    verdict=[]
    if r["zeros"]>=1024: verdict.append(f"零段{r['zeros']}")
    if r["dup"]<0.01 and r["ent"]<7.5: verdict.append("低熵+无重复")
    if r["paths"]: verdict.append("★明文路径串")
    tag=" / ".join(verdict) if verdict else "—"
    name=os.path.basename(f)[:50]
    print(f"{name:<52}{r['size']:>9}{r['zeros']:>9}{r['dup']*100:>7.2f}%{r['ent']:>7.3f}  {tag}")
    for p in r["paths"]: print(f"      └ {p[:100]}")
