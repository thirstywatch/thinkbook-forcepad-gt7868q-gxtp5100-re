import struct, re, zlib, bz2, lzma
p = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
b = open(p,"rb").read()

print("== 1) 全容器扫描 Cortex-M 向量表特征 ==")
hits=[]
for i in range(0, len(b)-160, 4):
    sp, rv = struct.unpack_from("<II", b, i)
    if 0x20000000 <= sp < 0x20040000 and (rv & 1) and 0x08000000 <= rv < 0x08020000:
        ok=0
        for k in range(2, 40):
            v = struct.unpack_from("<I", b, i+4*k)[0]
            if v == 0 or ((v & 1) and 0x08000000 <= v < 0x08020000): ok += 1
        if ok >= 30: hits.append((i, sp, rv, ok))
print("  候选数:", len(hits))
for i, sp, rv, ok in hits[:12]:
    inA = 0x113C <= i < 0x19A3C
    inB = 0x19A3C <= i < len(b)
    print("   off=0x%06X  SP=0x%08X  Reset=0x%08X  valid=%d  %s" % (i, sp, rv, ok, "载荷A内" if inA else ("载荷B内" if inB else "头部/元数据")))

print()
print("== 2) 载荷 A 体内的压缩/加密特征 ==")
A = b[0x113C:0x19A3C]
print("   载荷A 长度 0x%X" % len(A))
for name, magic in (("gzip",b"\x1f\x8b"),("zstd",b"\x28\xb5\x2f\xfd"),("lz4",b"\x04\x22\x4d\x18"),
                    ("bzip2",b"BZh"),("xz",b"\xfd7zXZ"),("zlib78",b"\x78\x9c"),("zlib78da",b"\x78\xda"),("zlib7801",b"\x78\x01")):
    pos=[m.start() for m in re.finditer(re.escape(magic), A)][:5]
    print("   %-9s magic 出现: %s" % (name, pos if pos else "无"))
for nm, fn in (("zlib",lambda x: zlib.decompress(x)),("raw-deflate",lambda x: zlib.decompress(x,-15)),
               ("bzip2",bz2.decompress),("lzma",lzma.decompress)):
    got=False
    for off in (0x40,0x80,0x100,0x1000,0x10000,0x18000):
        try:
            d=fn(A[off:]); print("   %s @0x%X -> %d 字节" % (nm,off,len(d))); got=True; break
        except Exception: pass
    if not got: print("   %s : 全失败" % nm)
try:
    import zstandard as zs
    for off in (0x40,0x80,0x100,0x1000):
        try:
            d=zs.ZstdDecompressor().decompress(A[off:], max_output_size=1<<22)
            print("   zstd @0x%X -> %d 字节" % (off,len(d))); break
        except Exception: pass
    else: print("   zstd : 全失败")
except ImportError: print("   zstandard 模块不可用")

print()
print("== 3) AES-ECB 迹象（16 字节块重复率）==")
blk=[A[i:i+16] for i in range(0x40, len(A)-16, 16)]
print("   块数 %d，去重后 %d，重复率 %.4f%%" % (len(blk), len(set(blk)), 100*(1-len(set(blk))/len(blk))))

print()
print("== 4) 明文前缀延伸到哪：找第一个高熵(采样)位置 ==")
import math, collections
def ent(x):
    c=collections.Counter(x); n=len(x)
    return -sum(v/n*math.log2(v/n) for v in c.values()) if n else 0
prev=None
for off in range(0, 0x20000, 0x400):
    e=ent(A[off:off+0x400])
    if e>7.5:
        print("   首个高熵窗口 @载荷A+0x%X (熵 %.2f)" % (off,e)); break
    prev=off
else: print("   前 0x20000 内未出现高熵窗口")
print("   载荷A 前 0x200 字节熵: %.2f" % ent(A[:0x200]))
