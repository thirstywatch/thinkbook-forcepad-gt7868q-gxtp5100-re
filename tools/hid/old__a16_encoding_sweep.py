import struct
BIN = r"<WORKSPACE>"
BASE_ADDR=0x08005000; BASE_OFF=0x19ABC
blob=open(BIN,'rb').read()
SEG=56480
seg=blob[BASE_OFF:BASE_OFF+SEG]
print("segment file range:", hex(BASE_OFF), "..", hex(BASE_OFF+SEG-1), " file size", hex(len(blob)))
print("segment IS the tail of the container?", BASE_OFF+SEG==len(blob))
print("listing covered up to ADDR 0x08012342; segment ends 0x%08X" % (BASE_ADDR+SEG-1))
print()

def decode_movw_imm(hw0, hw1):
    # Thumb-2 movw: 11110 i 10 0100 imm4 | 0 imm3 Rd imm8
    if (hw0 & 0xFB00) != 0xF200: return None      # 11110 x 10 0100
    i  = (hw0 >> 10) & 1
    imm4 = hw0 & 0xF
    imm3 = (hw1 >> 12) & 0x7
    Rd   = (hw1 >> 8) & 0xF
    imm8 = hw1 & 0xFF
    imm16 = (imm4 << 12) | (i << 11) | (imm3 << 8) | imm8
    return (Rd, imm16)
def decode_movt_imm(hw0, hw1):
    if (hw0 & 0xFB00) != 0xF2C0: return None      # 11110 x 10 1100
    i  = (hw0 >> 10) & 1
    imm4 = hw0 & 0xF
    imm3 = (hw1 >> 12) & 0x7
    Rd   = (hw1 >> 8) & 0xF
    imm8 = hw1 & 0xFF
    imm16 = (imm4 << 12) | (i << 11) | (imm3 << 8) | imm8
    return (Rd, imm16)

print("=== ALL movw sites building an immediate in 0x4000-0x5FFF  (whole segment, every 2-byte offset) ===")
sites=[]
for off in range(0, SEG-3, 2):
    hw0, hw1 = struct.unpack_from('<HH', seg, off)
    d = decode_movw_imm(hw0, hw1)
    if d and 0x4000 <= d[1] <= 0x5FFF:
        a = BASE_ADDR+off
        # look for a following movt on the same register within 6 halfwords
        val=None; how='movw-only'
        for k in range(2, 14, 2):
            if off+k+3 >= SEG: break
            g0,g1 = struct.unpack_from('<HH', seg, off+k)
            t = decode_movt_imm(g0,g1)
            if t and t[0]==d[0]:
                val = (t[1]<<16)|d[1]; how='movw+movt'; break
        sites.append((a, d[0], d[1], val, how))
for a,r,lo,val,how in sites:
    print(f"  {a:08X}  r{r}  movw #{lo:#06x}  {how}  -> {'' if val is None else hex(val)}")
print("  total movw sites in 0x4000-0x5FFF:", len(sites))
print()
print("=== sites whose RESOLVED 32-bit value lands in 0x40005400-0x40005BFF (I2C1/I2C2 region) ===")
for a,r,lo,val,how in sites:
    if val is not None and 0x40005400 <= val < 0x40005C00:
        print(f"  ** {a:08X} r{r} = {val:#010x}")
print()
print("=== sites whose movw imm == 0x5800 (I2C2 low half) ===")
for a,r,lo,val,how in sites:
    if lo == 0x5800: print(f"   {a:08X} r{r} -> {val}")
