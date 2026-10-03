import struct, re
BIN = r"<WORKSPACE>"
BASE_ADDR = 0x08005000; BASE_OFF = 0x19ABC
blob = open(BIN,'rb').read()
def addr(o): return o - BASE_OFF + BASE_ADDR
def off(a): return a - BASE_ADDR + BASE_OFF

targets = {
 0x0800894D: "I2C1_ER stub 0x800894C",
 0x08008979: "I2C1_EV stub 0x8008978 (ADDR)",
 0x080089A3: "stub 0x80089A2 (RxNE)",
 0x080089CB: "stub 0x80089CA (STOPF)",
 0x080089F3: "stub 0x80089F2 (TxE)",
 0x08008A1D: "0x8008A1C (AF handler)",
 0x08008B31: "0x8008B30 (ADDR handler)",
 0x08008A71: "0x8008A70 (RxNE handler)",
 0x08008A4D: "0x8008A4C (STOPF handler)",
 0x08008AE5: "0x8008AE4 (TxE handler)",
 0x08008B69: "0x8008B68 (I2C init)",
}
print("=== search raw container for these code pointers (any byte offset) ===")
for v,name in targets.items():
    pat = struct.pack('<I', v)
    hits = [m.start() for m in re.finditer(re.escape(pat), blob)]
    print(f"{name:34s} {v:#010x}  hits={len(hits)}  ->  {[hex(h) for h in hits]}  addr={[hex(addr(h)) for h in hits]}")

print()
print("=== search asm text for direct branch/ref to these addrs ===")
ASM = r"<WORKSPACE>"
pat = re.compile(r'0x8008(9[a-fA-F][0-9a-fA-F]|8[a-fA-F][0-9a-fA-F])')
for ln, raw in enumerate(open(ASM, encoding='utf-8', errors='replace'),1):
    if re.search(r'(bl|blx|b\.w|b|cbz|cbnz)\s+#0x8008(9|a|b)', raw):
        print(f"  line{ln:6d} {raw.strip()}")
