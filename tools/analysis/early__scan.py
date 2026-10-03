import struct, zstandard, io

PATH = r"C:/Windows/Firmware/TB14P_GT7868Q_14030522_20240202.BIN"
data = open(PATH, "rb").read()
n = len(data)
print("FILE_SIZE", n)
print("HEX SIZE", hex(n))

# 1) scan for zstd magic frames
MAGIC = b'\x28\xb5\x2f\xfd'
idx = 0
print("--- zstd magic occurrences ---")
while True:
    p = data.find(MAGIC, idx)
    if p < 0: break
    print("  zstd @", hex(p), "offset", p)
    idx = p + 1

# 2) scan for candidate ARM Cortex-M vector tables (LE 32-bit words)
# SP should be ~0x2000xxxx, reset vector ~0x0800xxxx with Thumb bit (lsb set)
def u32(b, o): return struct.unpack_from("<I", b, o)[0]
print("--- candidate vector tables (SP@0x2000.., Reset@0x0800..+thumb) ---")
for i in range(0, n-8, 4):
    sp = u32(data, i)
    rst = u32(data, i+4)
    if (0x20000000 <= sp <= 0x20010000) and (rst & 0xFF000000 == 0x08000000) and (rst & 1):
        # verify next entries point into flash too
        cnt = 0
        for k in range(2, 16):
            v = u32(data, i + k*4)
            if v == 0 or (v & 0xFF000000 == 0x08000000 and v & 1):
                cnt += 1
        if cnt >= 8:
            print("  VTABLE @", hex(i), "SP=", hex(sp), "Reset=", hex(rst), "good_vec=", cnt)
