import re, struct
SRC=r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"
mem=bytearray(0x10000)
for line in open(SRC,encoding="utf-8",errors="replace"):
    line=line.strip()
    m=re.match(r"^0x([0-9A-F]{4})\s+([0-9A-F ]+)$",line)
    if m:
        a=int(m.group(1),16); b=bytes.fromhex(m.group(2)); mem[a:a+len(b)]=b
print("=== 在 64KB 空间里找 MCU 侧的已知结构 ===")
pats = {
  "TIM2 结构 (base=0x40000000,amp=119,period=1999)": struct.pack("<III",0x40000000,119,1999),
  "TIM3 结构 (base=0x40000400,amp=119,period=999)":  struct.pack("<III",0x40000400,119,999),
  "TIM2 base 单独 0x40000000": struct.pack("<I",0x40000000),
  "TIM3 base 单独 0x40000400": struct.pack("<I",0x40000400),
  "GPIOB base 0x40010C00": struct.pack("<I",0x40010C00),
  "I2C1 base 0x40005400": struct.pack("<I",0x40005400),
  "119 (0x77) 作为 32 位": struct.pack("<I",119),
  "1999 (0x7CF) 作为 32 位": struct.pack("<I",1999),
  "999 (0x3E7) 作为 32 位": struct.pack("<I",999),
}
for nm,pat in pats.items():
    hits=[m.start() for m in re.finditer(re.escape(pat), bytes(mem))]
    print(f"  {nm:48s}: {len(hits)} 处 {[hex(h) for h in hits[:8]]}")
print()
print("=== 找 'TIM2 base 后跟 119' 的半结构 ===")
pat = struct.pack("<II",0x40000000,119)
hits=[m.start() for m in re.finditer(re.escape(pat), bytes(mem))]
print("  命中:", [hex(h) for h in hits[:8]])
print()
print("=== 找 0x4000xxxx 形式的 32 位值 (外设地址) ===")
found=[]
for a in range(0,0xFFFC):
    v=struct.unpack_from("<I",mem,a)[0]
    if 0x40000000 <= v < 0x40030000:
        found.append((a,v))
for a,v in found[:25]:
    print(f"  0x{a:04X} -> 0x{v:08X}")
print(f"  共 {len(found)} 处")
