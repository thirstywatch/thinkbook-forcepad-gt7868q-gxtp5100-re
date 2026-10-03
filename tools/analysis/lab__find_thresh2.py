import re, struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
DUMP=r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"
REC=1084
data=open(BIN,"rb").read()
mem=bytearray(0x10000)
for line in open(DUMP,encoding="utf-8",errors="replace"):
    m=re.match(r"^0x([0-9A-F]{4})\s+([0-9A-F ]+)$",line.strip())
    if m:
        a=int(m.group(1),16); b=bytes.fromhex(m.group(2)); mem[a:a+len(b)]=b

# 实测: HID 按下 141 / 松开 97 (比值 1.454)
# 若内部为原始域 = HID/2: 70 / 48
def ratio_ok(hi, lo):
    if lo <= 0 or hi <= lo: return False
    r = hi/lo
    return 1.30 <= r <= 1.60 and 40 <= hi <= 220

print("=== 配置记录中相邻 16 位值的'回滞阈值对'候选 ===")
for i in range(5):
    r=data[i*REC:(i+1)*REC]
    out=[]
    for k in range(0,REC-4,2):
        a=struct.unpack_from("<H",r,k)[0]
        b=struct.unpack_from("<H",r,k+2)[0]
        if ratio_ok(a,b) or ratio_ok(b,a):
            out.append((k,a,b))
    print(f"  记录{i}: {len(out)} 处")
    for k,a,b in out[:12]:
        ctx=" ".join(f"{x:02X}" for x in r[max(0,k-6):k+10])
        print(f"     +0x{k:03X}: {a:5d} / {b:5d}   上下文 {ctx}")

print("\n=== 传感器空间中的同类候选 (仅列前 25) ===")
n=0
for k in range(0,0xFFFC,2):
    a=struct.unpack_from("<H",mem,k)[0]
    b=struct.unpack_from("<H",mem,k+2)[0]
    if ratio_ok(a,b) and 55<=a<=170:
        print(f"  0x{k:04X}: {a:5d} / {b:5d}")
        n+=1
        if n>=25: break
print(f"  (共列出 {n} 处)")

print("\n=== 记录中'逐区阈值表'区域预览 (记录1, +0x1C0..+0x240) ===")
r1=data[1*REC:2*REC]
vals=[struct.unpack_from("<H",r1,k)[0] for k in range(0x1C0,0x240,2)]
print("  " + " ".join(f"{v}" for v in vals))
