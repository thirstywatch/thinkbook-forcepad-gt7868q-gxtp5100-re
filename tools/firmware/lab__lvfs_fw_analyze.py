import struct, math, re
FW=r"<LAB>\touchpad-lab\vendor\goodix-lvfs\GT7936L_16753412.bin"
b=open(FW,"rb").read(); n=len(b)
print(f"固件 {n} 字节; 前 32 字节: {b[:32].hex(' ')}")

def sum8(x):
    s=0
    for v in x: s=(s+v)&0xFFFF
    return s
def sum16le(x):
    s=0
    for k in range(0,len(x)-1,2): s=(s+struct.unpack_from("<H",x,k)[0])&0xFFFFFFFF
    return s

print("\n=== ① 试官方 GTX8 格式: checksum = sum8(buf[6:6+firmware_size]) ===")
ok=False
for size_off in range(0,12):
    for csum_off in range(0,12):
        if abs(size_off-csum_off)<4: continue
        for send in (">","<"):
            fw=struct.unpack_from(send+"I",b,size_off)[0]
            if not (1000<fw<n): continue
            for cend in (">","<"):
                c=struct.unpack_from(cend+"H",b,csum_off)[0]
                if sum8(b[6:6+fw])==c:
                    print(f"   ★ GTX8 命中: firmware_size@{size_off}({send})={fw}  checksum@{csum_off}({cend})=0x{c:04X}"); ok=True
if not ok: print("   GTX8 未命中")

print("\n=== ② 试官方 BRLB 格式: checksum = sum16le(buf[8:8+firmware_size]) ===")
ok2=False
for size_off in range(0,16):
    for csum_off in range(0,16):
        for send in (">","<"):
            fw=struct.unpack_from(send+"I",b,size_off)[0]
            if not (1000<fw<n): continue
            for cend in (">","<"):
                c=struct.unpack_from(cend+"I",b,csum_off)[0]
                if sum16le(b[8:8+fw])==c:
                    print(f"   ★ BRLB 命中: size@{size_off}({send})={fw} csum@{csum_off}({cend})=0x{c:08X}"); ok2=True
if not ok2: print("   BRLB 未命中")

print("\n=== ③ HID 描述符特征搜索 (触觉相关) ===")
pats={
 "Haptics 用法页 06 0E 00": bytes.fromhex("060E00"),
 "Manual Trigger 09 21": bytes.fromhex("0921"),
 "Waveform List 09 10": bytes.fromhex("0910"),
 "Intensity 09 23": bytes.fromhex("0923"),
 "触控板集合 05 0D 09 05 A1 01": bytes.fromhex("050D0905A101"),
 "厂商页 06 00 FF": bytes.fromhex("0600FF"),
 "集合序 A1 01 85": bytes.fromhex("A10185"),
}
for nm,p in pats.items():
    hits=[m.start() for m in re.finditer(re.escape(p), b)]
    print(f"   {nm:28s}: {len(hits)} 处 {[hex(h) for h in hits[:6]]}")

print("\n=== ④ 字符串 ===")
kws=re.compile(rb"(?i)(goodix|gt79|gt78|version|haptic|waveform|trigger|touch)")
cnt=0
for m in re.finditer(rb"[\x20-\x7E]{6,}", b):
    if kws.search(m.group()):
        print(f"   0x{m.start():06X}: {m.group().decode('ascii','replace')[:70]}")
        cnt+=1
        if cnt>=20: break
if cnt==0: print("   (无)")

print("\n=== ⑤ 熵分布 (每 16KB) ===")
for off in range(0,n,16384):
    blk=b[off:off+16384]
    cc={}
    for x in blk: cc[x]=cc.get(x,0)+1
    H=-sum((v/len(blk))*math.log2(v/len(blk)) for v in cc.values())
    tag=" <== 高熵(加密?)" if H>7.5 else ""
    print(f"   0x{off:06X} H={H:5.2f}{tag}")
