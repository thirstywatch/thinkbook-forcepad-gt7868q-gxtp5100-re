import re, struct
LOG=r"<LAB>\touchpad-lab\poc\press-log.txt"
rep=[]
for line in open(LOG,encoding="utf-8",errors="replace"):
    m=re.match(r"^RPT .*?len=(\d+) cnt=(\d+) data= (.*)$",line.strip())
    if m: rep.append((int(m.group(2)), bytes.fromhex(m.group(3).replace(" ",""))))
print("报文数:", len(rep))
P=lambda b: struct.unpack_from("<H", b, 6)[0]
cnts=set(c for c,_ in rep)
print("触点数字段 cnt 取值:", sorted(cnts)[:10])
# 逐位扫描：统计跳变次数，并记录上升沿前后的压力
print("\n=== 跳变次数在 4~40 之间的位 (可能是按键位) ===")
best=[]
for bit in range(0, 16*8):
    tr=[]; prev=None
    for i,(c,b) in enumerate(rep):
        v=(b[bit//8]>>(bit%8))&1
        if prev is not None and v!=prev: tr.append((i,v))
        prev=v
    if 4 <= len(tr) <= 40:
        rises=[i for i,v in tr if v==1]
        # 上升沿前后压力差
        diffs=[]
        for i in rises:
            p0=P(rep[max(0,i-3)][1]); p1=P(rep[min(len(rep)-1,i+3)][1])
            diffs.append(abs(p1-p0))
        best.append((sum(diffs)/len(diffs) if diffs else 0, bit, len(tr), rises[:6]))
best.sort(reverse=True)
for avgd,bit,nt,rises in best[:10]:
    print(f"  byte{bit//8:2d}.bit{bit%8}  跳变{nt:3d}  上升沿处压力平均变化={avgd:6.1f}  上升沿序号={rises}")
# 顺带：cnt 字段变化
print("\n=== 触点数字段(cnt)变化 ===")
prev=None
for i,(c,b) in enumerate(rep):
    if prev is not None and c!=prev: print(f"  [{i}] cnt {prev} -> {c}  压力={P(b)}")
    prev=c
# 压力超过各阈值的首个序号
print("\n=== 压力首次超过阈值的时刻 (看按下点落在哪) ===")
for th in (100,200,300,400,450):
    for i,(c,b) in enumerate(rep):
        if P(b)>=th:
            print(f"  首次 >= {th}: 序号 {i}"); break
print("\n=== 前 60 条 (压力 / byte0..byte3) ===")
for i,(c,b) in enumerate(rep[:60]):
    print(f"  [{i:3d}] P={P(b):4d} cnt={c} b={b[:4].hex(' ')}")
