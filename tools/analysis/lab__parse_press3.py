import re, struct
LOG=r"<LAB>\touchpad-lab\poc\press-log.txt"
rep=[]
for line in open(LOG,encoding="utf-8",errors="replace"):
    m=re.match(r"^RPT .*?len=(\d+) cnt=(\d+) data= (.*)$",line.strip())
    if m: rep.append((int(m.group(2)), bytes.fromhex(m.group(3).replace(" ",""))))
print("报文数:", len(rep))
P=lambda b: struct.unpack_from("<H", b, 6)[0]
if not rep: raise SystemExit("无报文")
print("压力范围: max=", max(P(b) for _,b in rep))
# byte39.bit0 = 按键位 (基线时上升沿压力≈141)
prev=None; rises=[]; falls=[]
for i,(c,b) in enumerate(rep):
    v=b[39]&1
    if prev is not None and v!=prev:
        (rises if v==1 else falls).append(P(b))
    prev=v
print("\n按键位 (byte39.bit0) 跳变:")
print("  按下瞬间压力:", rises)
print("  松开瞬间压力:", falls)
print("\n=== 与基线对比 ===")
print("  基线: 按下 140-149 (中位 ~141)   松开 75-99 (~97)")
if rises:
    sr=sorted(rises)
    print(f"  本次: 按下 min={min(rises)} max={max(rises)} 中位={sr[len(sr)//2]}  样本数={len(rises)}")
if falls:
    sf=sorted(falls)
    print(f"  本次: 松开 min={min(falls)} max={max(falls)} 中位={sf[len(sf)//2]}")
# 逐字节差异检查: 看报文里有没有别的位/字段变化(比如多了个位)
print("\n=== 报文长度与 byte36-39 样例 ===")
print("  长度:", len(rep[0][1]))
for i in range(0, min(len(rep), 600), 100):
    c,b=rep[i]
    print(f"  [{i:4d}] P={P(b):4d} b36..39={b[36]:02X} {b[37]:02X} {b[38]:02X} {b[39]:02X}")
