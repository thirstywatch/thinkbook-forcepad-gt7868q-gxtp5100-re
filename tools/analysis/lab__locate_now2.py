import re, struct
DUMP=r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"
mem=bytearray(0x10000)
for line in open(DUMP,encoding="utf-8",errors="replace"):
    m=re.match(r"^0x([0-9A-F]{4})\s+([0-9A-F ]+)$",line.strip())
    if m:
        a=int(m.group(1),16); b=bytes.fromhex(m.group(2)); mem[a:a+len(b)]=b
pats={
 "阈值对 30 00 30 00 46 00 46 00 (48,48,70,70)": bytes.fromhex("30003000" "46004600"),
 "仅 46 00 46 00 (70,70)": bytes.fromhex("46004600"),
 "90,80,48,48 5A 00 50 00 30 00 30 00": bytes.fromhex("5A005000" "30003000"),
}
for nm,pat in pats.items():
    hits=[]; s=0
    while True:
        j=mem.find(pat,s)
        if j<0: break
        hits.append(j); s=j+1
    print(f"  {nm}: {len(hits)} 处 {[hex(h) for h in hits[:12]]}")
print("\n=== 0x5A00 附近当前内容 (对照上次 0x5A08) ===")
for k in range(0x59F0,0x5A50,16):
    print(f"  0x{k:04X}: {' '.join(f'{b:02X}' for b in mem[k:k+16])}")
print("\n=== 找所有含 0x46(70) 连续 3+ 个 16 位值的位置 ===")
out=[]
for k in range(0,0xFFF0,2):
    n=0
    while k+2*n < 0x10000 and struct.unpack_from("<H",mem,k+2*n)[0]==70: n+=1
    if n>=3: out.append((k,n))
print(f"  {len(out)} 处: {[(hex(a),n) for a,n in out[:20]]}")
