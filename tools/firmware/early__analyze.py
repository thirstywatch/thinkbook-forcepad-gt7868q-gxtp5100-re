import sys, os

SRC = r"C:/Windows/System32/DriverStore/FileRepository/goodixtouchpad.inf_amd64_dd57a59bc9759d61/TB14P_GT7868Q_14030522_20240202.BIN"
data = open(SRC, "rb").read()
n = len(data)
print("file:", os.path.basename(SRC))
print("size:", n, "bytes (0x%X)" % n)

def u32(b, o):
    return b[o] | b[o+1] << 8 | b[o+2] << 16 | b[o+3] << 24

# 1) Cortex-M vector table candidates: SP=0x2000xxxx, Reset=0x0800xxxx
print("\n=== Cortex-M vector-table candidates (SP=0x2000.., Reset=0x0800..) ===")
hits = []
for o in range(0, n - 8):
    if data[o+2] == 0x00 and data[o+3] == 0x20 and data[o+6] == 0x00 and data[o+7] == 0x08:
        sp = u32(data, o); rst = u32(data, o+4)
        hits.append(o)
        print("  off=0x%05X (%d) SP=0x%08X Reset=0x%08X" % (o, o, sp, rst))
if not hits:
    print("  (none found with strict 0x20/0x08 mask)")

# 2) entropy map in 1KB windows
def entropy(b):
    from math import log2
    if not b: return 0.0
    cnt = [0] * 256
    for x in b: cnt[x] += 1
    e = 0.0
    for c in cnt:
        if c:
            p = c / len(b); e -= p * log2(p)
    return e

print("\n=== entropy map (1KB windows, 8=max) ===")
W = 1024
for s in range(0, n, W):
    e = entropy(data[s:s+W])
    bar = "#" * int(e * 8)
    print("  0x%05X-0x%05X  E=%.2f %s" % (s, min(s+W, n), e, bar))

# 3) last 128 bytes (look for truncated end / 0xFF padding)
print("\n=== last 128 bytes (hex) ===")
tail = data[-128:]
print("  " + tail.hex())

# 4) trailing 0xFF run length (flash padding would be 0xFF; truncation would NOT be 0xFF)
i = n
while i > 0 and data[i-1] == 0xFF:
    i -= 1
print("\n  trailing 0xFF count from end:", n - i)
print("  last non-0xFF offset:", i-1, "(0x%X)" % (i-1))
