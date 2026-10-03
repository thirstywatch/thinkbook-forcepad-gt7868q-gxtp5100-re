import json,re,glob,os
# 解析落盘的评论 JSON
cands=glob.glob(r"<HOME>\AppData\Local\Temp\dsh-spill-*\session-*\*web_fetch.txt")
cands.sort(key=os.path.getmtime, reverse=True)
print("候选文件:", len(cands))
for p in cands[:2]:
    txt=open(p,encoding='utf-8',errors='ignore').read()
    m=re.search(r'\{"code":0.*',txt,re.S)
    if not m: continue
    raw=m.group(0)
    # 尽力解析
    try:
        d=json.loads(raw[:raw.rfind('}')+1])
    except Exception:
        # 截断：手动抓 message
        msgs=re.findall(r'"uname":"([^"]*)".*?"message":"((?:[^"\\]|\\.)*)"', raw)
        print(f"\n[{os.path.basename(p)}] 手动抓取 {len(msgs)} 条")
        for u,msg in msgs:
            msg=msg.encode().decode('unicode_escape',errors='ignore')
            print(f"  @{u}: {msg[:200]}")
        continue
    reps=d.get('data',{}).get('replies',[])
    print(f"\n[{os.path.basename(p)}] 解析到 {len(reps)} 条顶层评论")
    for r in reps:
        print(f"  ♥{r.get('like',0):3d} @{r['member']['uname']}: {r['content']['message'][:200]}")
        for sub in (r.get('replies') or []):
            print(f"        └ @{sub['member']['uname']}: {sub['content']['message'][:180]}")
