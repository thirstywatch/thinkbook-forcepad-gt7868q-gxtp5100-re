import math, collections, zlib, struct
p = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
b = open(p,"rb").read()
print("total", len(b), "  0x19ABC =", 0x19ABC, "  97*1084 =", 97*1084)
def ent(x):
    if not x: return 0
    c = collections.Counter(x); n = len(x)
    return -sum(v/n*math.log2(v/n) for v in c.values())
print("head 64 bytes:", b[:64].hex())
print("head 1084B entropy: %.3f" % ent(b[:1084]))
print("--- per-block entropy (step 12) ---")
for i in range(0, 97, 12):
    print("  blk %2d  ent=%.3f  first16=%s" % (i, ent(b[i*1084:(i+1)*1084]), b[i*1084:i*1084+16].hex()))
print("--- block 0 vs block 1 first 32 bytes ---")
print("  b0:", b[0:32].hex())
print("  b1:", b[1084:1116].hex())
print("--- plaintext region entropy ---")
print("  0x19ABC+0..4096: %.3f" % ent(b[0x19ABC:0x19ABC+4096]))
print("  0x19ABC-4096..: %.3f" % ent(b[0x19ABC-4096:0x19ABC]))
print("--- try decompress block 0 ---")
blk = b[0:1084]
for name, w in (("zlib",15),("raw-deflate",-15),("gzip",31)):
    try:
        d = zlib.decompress(blk, w); print("  %s OK -> %d bytes" % (name, len(d)))
    except Exception as e:
        print("  %s fail" % name)
try:
    import lzma
    print("  lzma:", len(lzma.decompress(blk)))
except Exception: print("  lzma fail")
print("--- 0x19ABC 处前 32 字节 ---")
print(" ", b[0x19ABC:0x19ABC+32].hex())
