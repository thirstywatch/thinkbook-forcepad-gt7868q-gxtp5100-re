"""压测：GT7868Q 的 ~100KB"加密区"到底是【加密】还是【压缩】？
若是标准压缩流 => 不需要任何密钥。
"""
import os, zlib, bz2, lzma, gzip, io, struct, collections, math

BIN = r"<WORKSPACE>"
d = open(BIN, "rb").read()
print("容器大小 =", len(d))

# 项目文档给的两种边界都试
REGIONS = [("0x1400..0x19A00", 0x1400, 0x19A00), ("0x123C..0x19A3C", 0x123C, 0x19A3C)]

def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())

def repeated_blocks(b, bs=16):
    seen = collections.Counter()
    for i in range(0, len(b) - bs + 1, bs):
        seen[b[i:i + bs]] += 1
    tot = sum(seen.values())
    rep = sum(v for v in seen.values() if v > 1)
    return rep, tot, (rep / tot if tot else 0)

for name, lo, hi in REGIONS:
    seg = d[lo:hi]
    print("\n" + "=" * 74)
    print("区间 %s  长度 %d (0x%X)" % (name, len(seg), len(seg)))
    print("  熵 = %.3f  前 32 B = %s" % (entropy(seg), " ".join("%02X" % c for c in seg[:32])))
    rep, tot, frac = repeated_blocks(seg)
    print("  16 字节块：总 %d，重复参与 %d，重复率 %.2f%%" % (tot, rep, frac * 100))

    # --- 试各种解压 ---
    tries = []
    tries.append(("zlib", lambda s: zlib.decompress(s)))
    tries.append(("deflate(raw)", lambda s: zlib.decompressobj(-15).decompress(s)))
    tries.append(("gzip", lambda s: gzip.decompress(s)))
    tries.append(("bz2", lambda s: bz2.decompress(s)))
    tries.append(("lzma(xz)", lambda s: lzma.decompress(s)))
    tries.append(("lzma(alone)", lambda s: lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(s)))
    for mod, fn in (("lz4.block", lambda s: __import__("lz4.block", fromlist=["x"]).decompress(s)),
                    ("lz4.frame", lambda s: __import__("lz4.frame", fromlist=["x"]).decompress(s)),
                    ("zstandard", lambda s: __import__("zstandard").ZstdDecompressor().decompress(s)),
                    ("snappy", lambda s: __import__("snappy").uncompress(s)),
                    ("brotli", lambda s: __import__("brotli").decompress(s))):
        try:
            __import__(mod.split(".")[0])
            tries.append((mod, fn))
        except Exception:
            pass
    ok = False
    for nm, fn in tries:
        try:
            out = fn(seg)
            if out and len(out) > 64:
                print("  ★★ %s 解压成功！%d -> %d 字节，头 32B: %s" % (nm, len(seg), len(out), " ".join("%02X" % c for c in out[:32])))
                ok = True
            else:
                print("  %-14s 返回空/过短" % nm)
        except Exception as e:
            print("  %-14s 失败: %s" % (nm, str(e)[:60]))
    if not ok:
        print("  ⇒ 标准解压全部失败")

    # --- 扫内部是否藏常见格式 magic ---
    MAGICS = {b"\x1f\x8b": "gzip", b"\xfd7zXZ": "xz", b"BZh": "bzip2", b"\x28\xb5\x2f\xfd": "zstd",
              b"\x04\x22\x4d\x18": "lz4", b"PK\x03\x04": "zip", b"7z\xbc\xaf": "7z",
              b"\x89PNG": "png", b"\xff\xd8\xff": "jpeg", b"CFU": "CFU?", b"YELSTO": "YELSTO",
              b"\x5d\x00\x00": "lzma-alone-hdr", b"\x02\x00\x00\x00": "?", b"MSS1": "MSS1", b"SAML": "SAML"}
    hits = []
    for mg, nm in MAGICS.items():
        i = seg.find(mg)
        if i >= 0:
            hits.append("%s@+0x%X" % (nm, i))
    print("  内部 magic 命中：", ", ".join(hits) if hits else "无")

    # --- 探针：若真是 ECB 且明文含大量重复块，则"密文块值"应高度集中 ---
    seen = collections.Counter(seg[i:i + 16] for i in range(0, len(seg) - 15, 16))
    top = seen.most_common(3)
    print("  最常见的 16B 块出现次数：", [(v, "…") for _, v in top])
