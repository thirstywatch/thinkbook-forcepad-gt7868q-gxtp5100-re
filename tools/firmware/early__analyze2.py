import sys, os, re
from math import log2

SRC = r"<WORKSPACE>"
data = open(SRC, "rb").read()
n = len(data)
print("file:", os.path.basename(SRC))
print("size:", n, "bytes (0x%X)" % n)

def u32(b, o):
    return b[o] | b[o+1] << 8 | b[o+2] << 16 | b[o+3] << 24

# 1) Cortex-M vector table: SP in 0x20000000..0x2000FFFF, Reset in 0x08000000..0x080FFFFF (LSB=1)
print("\n=== Cortex-M vector-table candidates ===")
cnt = 0
for o in range(0, n - 8, 4):
    sp = u32(data, o); rst = u32(data, o+4)
    if (0x20000000 <= sp <= 0x2000FFFF) and (0x08000000 <= rst <= 0x080FFFFF) and (rst & 1):
        cnt += 1
        print("  off=0x%05X SP=0x%08X Reset=0x%08X" % (o, sp, rst))
print("  total:", cnt)

# 2) Taifang signature strings
print("\n=== Taifang / version signatures ===")
for pat in [b"TF100A_Test_FW", b"TF100A", b"TF100", b"Taifang", b"TAIFANG"]:
    idx = 0
    found = []
    while True:
        i = data.find(pat, idx)
        if i < 0: break
        found.append(i); idx = i + 1
    if found:
        print("  %-16s -> %d hit(s): %s" % (pat, len(found), [hex(x) for x in found[:10]]))
        for x in found[:3]:
            s = data[x:x+40]
            print("      @0x%X: %r" % (x, s))
# version like 5.21.01.23007
for m in re.finditer(rb"5\.21\.01\.\d{4,6}", data):
    print("  version @0x%X: %r" % (m.start(), m.group()))
for m in re.finditer(rb"20\d\d-\d\d-\d\d[ \t]\d\d:\d\d:\d\d", data):
    print("  timestamp @0x%X: %r" % (m.start(), m.group()))

# 3) entropy map (1KB)
def entropy(b):
    if not b: return 0.0
    cnt = [0]*256
    for x in b: cnt[x]+=1
    e=0.0
    for c in cnt:
        if c:
            p=c/len(b); e-=p*log2(p)
    return e
print("\n=== entropy map (1KB windows, 8=max) ===")
W=1024
for s in range(0, n, W):
    e=entropy(data[s:s+W])
    print("  0x%05X-0x%05X E=%.2f %s" % (s, min(s+W,n), e, "#"*int(e*8)))

# 4) low-entropy (plaintext) regions ascii dump
print("\n=== ASCII strings length>=6 (first 60) ===")
strings = re.findall(rb"[ -~]{6,}", data)
for s in strings[:60]:
    print("  ", s.decode('latin1'))
print("  ... total strings:", len(strings))

# 5) tail inspection
print("\n=== tail 64 bytes ===")
print("  " + data[-64:].hex())
i=n
while i>0 and data[i-1]==0xFF: i-=1
print("  trailing 0xFF count:", n-i, " last non-FF off: 0x%X" % (i-1))
