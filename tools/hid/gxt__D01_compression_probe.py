# -*- coding: utf-8 -*-
"""D01. 压缩可能性排查 (被忽略方向)。
检查: LZMA/zlib/gzip/LZ4/LZO/QuickLZ/HeatShrink 魔数 + 各区段尝试解压。
关键点: 96KB 高熵区如果真是压缩数据, 应能被某种解压器吐出"合理长度"的输出,
        或至少出现压缩头。
"""
import sys, os, zlib, bz2, lzma, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load(); N = len(FW)

MAGIC = {
    "gzip 1F8B": bytes.fromhex("1f8b"),
    "zlib 7801": bytes.fromhex("7801"), "zlib 789C": bytes.fromhex("789c"),
    "zlib 78DA": bytes.fromhex("78da"), "zlib 785E": bytes.fromhex("785e"),
    "zlib 78A5": bytes.fromhex("78a5"), "zlib 78F9": bytes.fromhex("78f9"),
    "zlib 785E/78A5": None,
    "LZ4 frame 04224D18": bytes.fromhex("04224d18"),
    "LZ4 skippable 184D2204": bytes.fromhex("184d2204"),
    "LZMA/XZ FD377A585A00": bytes.fromhex("fd377a585a00"),
    "LZMA-Alone 5D0000": bytes.fromhex("5d0000"),
    "7z 377ABCAF271C": bytes.fromhex("377abcaf271c"),
    "bzip2 BZh": b"BZh",
    "Zstd 28B52FFD": bytes.fromhex("28b52ffd"),
    "Snappy stream": bytes.fromhex("ff060000734e61507059"),
    "LZO 1x": None,
    "lzfse": b"bvx-", "lzfse2": b"bvx1",
    "lzop 894c5a4f": bytes.fromhex("894c5a4f"),
    "LZMA raw prop 5D 00 00": bytes.fromhex("5d0000"),
    "zlib 7801 2nd": None,
}
print("=" * 96)
print("D01-a. 常见压缩魔数全文件搜索")
print("=" * 96)
for name, m in MAGIC.items():
    if m is None: continue
    hits = []; st = 0
    while True:
        k = FW.find(m, st)
        if k < 0: break
        hits.append(k); st = k + 1
    if hits:
        print(f"  {name:26s} 命中 {len(hits):>3d} 次 -> {[hex(h) for h in hits[:10]]}")
    else:
        print(f"  {name:26s} 未找到")

print("\n" + "=" * 96)
print("D01-b. ★ 在多个候选起点尝试真实解压 (zlib/bz2/lzma) —— 判据: 输出 >512B 且可打印率>0.5")
print("=" * 96)
def try_all(off, ln=20000):
    buf = FW[off:off+ln]
    out = []
    # raw deflate / zlib / gzip
    for tag, fn in [
        ("zlib", lambda b: zlib.decompress(b)),
        ("deflate-raw", lambda b: zlib.decompress(b, -15)),
        ("gzip", lambda b: zlib.decompress(b, 16+15)),
        ("bz2", lambda b: bz2.decompress(b)),
        ("lzma", lambda b: lzma.decompress(b)),
        ("lzma-fmt-alone", lambda b: lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(b)),
        ("lzma-fmt-raw", lambda b: lzma.LZMADecompressor(format=lzma.FORMAT_RAW,
             filters=[{"id": lzma.FILTER_LZMA1, "dict_size": 1<<16}]).decompress(b)),
    ]:
        try:
            r = fn(buf)
            if len(r) > 512:
                out.append((tag, len(r), printable_ratio(r)))
        except Exception:
            pass
    return out

starts = [0x00000, 0x00080, 0x00100, 0x00200, 0x00400, 0x00800, 0x01000, 0x01200,
          0x02000, 0x04000, 0x08000, 0x10000, 0x18000, 0x19000, 0x19850, 0x19A00]
anyfound = False
for off in starts:
    r = try_all(off)
    if r:
        anyfound = True
        print(f"  0x{off:05X}: {r}")
if not anyfound:
    print("  ★ 所有候选起点: 没有任何解压器输出 >512 B 的结果 -> 无标准压缩容器")

print("\n" + "=" * 96)
print("D01-c. ★ 无头/裸流暴力尝试 (所有常见起点 × lzma raw 各种参数)")
print("=" * 96)
found = 0
filters = []
for dict_size in (1<<12, 1<<14, 1<<16, 1<<20, 1<<23):
    for lc in (0, 1, 3):
        for lp in (0, 2):
            for pb in (0, 2):
                if lc + lp > 4: continue
                filters.append({"id": lzma.FILTER_LZMA1, "dict_size": dict_size,
                                "lc": lc, "lp": lp, "pb": pb})
print(f"  测试 {len(filters)} 种 LZMA raw 参数 × {len(starts)} 起点 ...")
for off in [0x01200, 0x02000, 0x04000, 0x08000, 0x10000, 0x19850]:
    buf = FW[off:off+8192]
    for f in filters:
        try:
            r = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[f]).decompress(buf)
            if len(r) > 1024:
                print(f"    ★ 命中! off=0x{off:05X} 参数={f} 输出={len(r)}B")
                found += 1
        except Exception:
            pass
print(f"  LZMA raw 暴力命中数 = {found}")

print("\n" + "=" * 96)
print("D01-d. ★ Thumb 函数序言固定步长检测 (压缩数据不会有规律步长)")
print("=" * 96)
# 常见序言: push {...,lr} = b5xx / b4xx; stmdb sp!,{...} = 2de9/e92d
prologues = [(0xb5, "b5xx push{lr}"), (0xb4, "b4xx push"), (0x2d, "2de9 stmdb"),
             (0xe9, "e92d stmdb big"), (0xb5, "b5xx")]
for off, ln in [(0x01200, 0x10000), (0x02000, 0x8000), (0x08000, 0x8000),
                (0x10000, 0x8000), (0x19850, 0x8000)]:
    buf = FW[off:off+ln]
    for pb, name in prologues[:2]:
        pos = [i for i in range(0, len(buf)-2, 2) if buf[i] == pb]
        if len(pos) < 3: 
            print(f"  0x{off:05X} {name}: 出现 {len(pos)} 次 (太少)")
            continue
        gaps = [pos[i+1]-pos[i] for i in range(len(pos)-1)]
        from collections import Counter
        c = Counter(gaps)
        top = c.most_common(3)
        # 固定步长: 某个 gap 占比 > 0.25
        fixed = any(v/len(gaps) > 0.25 for _, v in top)
        print(f"  0x{off:05X} {name}: n={len(pos):>5d} 间隔众数={top} "
              f"{'<<< 有固定步长' if fixed else '(无固定步长)'}")

print("\n" + "=" * 96)
print("D01-e. 参考系: 把 0x19850-0x26500 的真代码区做同一序言检测 (应出现固定步长)")
print("=" * 96)
buf = FW[0x19850:0x1A000]
for pb, name in prologues[:2]:
    pos = [i for i in range(0, len(buf)-2, 2) if buf[i] == pb]
    from collections import Counter
    if pos:
        gaps = [pos[i+1]-pos[i] for i in range(len(pos)-1)]
        print(f"  {name}: n={len(pos)} 间隔={Counter(gaps).most_common(4)}")
