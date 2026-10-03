import struct
BIN=r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
buf=open(BIN,"rb").read(); n=len(buf)
def sum8(b):
    s=0
    for x in b: s=(s+x)&0xFFFF
    return s
def sum16le(b):
    s=0
    for k in range(0,len(b)-1,2): s=(s+struct.unpack_from("<H",b,k)[0])&0xFFFFFFFF
    return s
print(f"文件 {n} 字节; 前 8 字节: {buf[:8].hex(' ')}")

print("\n=== A) BRLB 主头: checksum = sum16le(buf[8:firmware_size]) ===")
cands=[]
for fw in list(range(1000, n, 2)) + [105148, 105148+8, n-56480, n-56480+8]:
    if fw <= 8 or fw > n: continue
    c = sum16le(buf[8:fw])
    for off in (0, 2, 4):
        for end in ("<", ">"):
            v = struct.unpack_from(end+"I", buf, off)[0]
            if v == c:
                cands.append((fw, off, end, hex(v)))
seen=set(); out=[]
for fw,off,end,v in cands:
    k=(fw,off,end)
    if k in seen: continue
    seen.add(k); out.append((fw,off,end,v))
print(f"  命中 {len(out)}: {out[:8]}")

print("\n=== B) BRLB config 组: 位置 S, checksum(16位) == sum8(buf[S+6:]) ===")
hits=[]
for S in range(512, n-8):
    c = sum8(buf[S+6:])
    for off in (0, 2, 4):
        for end in ("<", ">"):
            v=struct.unpack_from(end+"H",buf,S+off)[0]
            if v==c: hits.append((S, off, end, c, buf[S+6], buf[S+7] if S+7<n else 0))
print(f"  命中 {len(hits)}: {[(hex(s),o,e,hex(c)) for s,o,e,c,_,_ in hits[:6]]}")

print("\n=== C) 关键切分点 105148 处到底是什么 ===")
S=105148
print(f"   buf[S-8:S]   = {buf[S-8:S].hex(' ')}")
print(f"   buf[S:S+16]  = {buf[S:S+16].hex(' ')}   <- 像向量表: SP=0x{buf[S+3]:02X}{buf[S+2]:02X}{buf[S+1]:02X}{buf[S]:02X}")
print(f"   sum8(buf[S+6:])  = 0x{sum8(buf[S+6:]):04X}")
print(f"   sum16le(buf[S+6:]) = 0x{sum16le(buf[S+6:]):08X}")
print(f"   文件头前 4 字节 (BE/LE) = 0x{struct.unpack_from('>I',buf,0)[0]:08X} / 0x{struct.unpack_from('<I',buf,0)[0]:08X}")
