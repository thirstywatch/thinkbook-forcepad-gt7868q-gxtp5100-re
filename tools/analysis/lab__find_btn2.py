import re, struct
LOG=r"<LAB>\touchpad-lab\poc\press-log.txt"
rep=[]
for line in open(LOG,encoding="utf-8",errors="replace"):
    m=re.match(r"^RPT .*?len=(\d+) cnt=(\d+) data= (.*)$",line.strip())
    if m: rep.append((int(m.group(2)), bytes.fromhex(m.group(3).replace(" ",""))))
P=lambda b: struct.unpack_from("<H", b, 6)[0]
print("报文数:", len(rep), " 长度:", len(rep[0][1]))
print("\n=== 全报文 320 位扫描: 跳变 8~14 次的位 ===")
for bit in range(0, len(rep[0][1])*8):
    tr=[]; prev=None
    for i,(c,b) in enumerate(rep):
        v=(b[bit//8]>>(bit%8))&1
        if prev is not None and v!=prev: tr.append((i,v))
        prev=v
    if 8 <= len(tr) <= 14:
        rises=[i for i,v in tr if v==1]
        ps=[P(rep[i][1]) for i in rises]
        print(f"  byte{bit//8}.bit{bit%8} 跳变{len(tr)} 上升沿序号={rises} 对应压力={ps}")
print("\n=== 若定位到按键位, 打印每次按下的完整压力曲线 ===")
# 取最后一个字节作为候选, 打印其时间线
lastbyte=len(rep[0][1])-1
prev=None
for i,(c,b) in enumerate(rep):
    v=(b[lastbyte]&1)
    if prev is not None and v!=prev:
        print(f"  [{i}] byte{lastbyte}.bit0 {prev}->{v}  压力={P(b)}")
    prev=v
print("\n=== byte36-39 时间线 (每 20 条, 含压力) ===")
for i in range(0, min(len(rep), 1200), 60):
    c,b=rep[i]
    print(f"  [{i:4d}] P={P(b):4d}  b36..39={b[36]:02X} {b[37]:02X} {b[38]:02X} {b[39]:02X}")
