import re, struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
DUMP=r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"
REC=1084
data=open(BIN,"rb").read(); r1=data[1*REC:2*REC]
mem=bytearray(0x10000)
for line in open(DUMP,encoding="utf-8",errors="replace"):
    m=re.match(r"^0x([0-9A-F]{4})\s+([0-9A-F ]+)$",line.strip())
    if m:
        a=int(m.group(1),16); b=bytes.fromhex(m.group(2)); mem[a:a+len(b)]=b
anchor=r1[0x280:0x280+16]
hits=[]
s=0
while True:
    j=mem.find(anchor,s)
    if j<0: break
    hits.append(j); s=j+1
print("记录1 +0x280 的 16 字节锚点:", anchor.hex(' '))
print("在当前传感器空间中的落点:", [hex(h) for h in hits])
for h in hits:
    tail_off = h + (0x2AC-0x280)
    print(f"\n  落点 0x{h:04X} -> 阈值字段应在 0x{tail_off:04X}")
    seg = mem[h:h+(0x2C0-0x280)]
    print("  该处原始字节:", seg.hex(' '))
    print("  16位小端:", " ".join(str(struct.unpack_from('<H',mem,h+k)[0]) for k in range(0,len(seg)-1,2)))
print("\n=== 期望值 (记录1 +0x280..+0x2C0) ===")
seg2=r1[0x280:0x2C0]
print("  字节:", seg2.hex(' '))
print("  16位小端:", " ".join(str(struct.unpack_from('<H',r1,0x280+k)[0]) for k in range(0,len(seg2)-1,2)))
