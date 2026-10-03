"""GT7868Q 主体性质终判 + 跨段线索。

假设检验：
 H1 压缩：搜压缩魔数；试 zlib/lzma/lz4 解压，看熵是否下降
 H2 数据表：0xB4 / 0x5A 等值的位置分布是否聚集（若是表，会成群）
 H3 跨段同源：GT7868Q 主体里是否出现 TF100A 的外设基址 / 字符串
 H4 「TF100A_Test_FW」说明这段是测试固件 —— 检查 GT7868Q 段是否也有类似标识
"""
import os
import re
import collections
import zlib
import lzma

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
GQ = d[0x1200:0x19800]
TF = d[0x19800:]


def ent(b):
    if not b:
        return 0.0
    import math
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


print("=" * 94)
print("H1 压缩假设：魔数 + 解压尝试")
print("=" * 94)
MAGIC = {
    "zlib(78 9C)": b"\x78\x9c", "zlib(78 01)": b"\x78\x01", "zlib(78 DA)": b"\x78\xda",
    "gzip(1F 8B)": b"\x1f\x8b", "lzma(FD 37 7A)": b"\xfd7zXZ",
    "lz4(04 22 4D 18)": b"\x04\x22\x4d\x18", "zstd(28 B5 2F FD)": b"\x28\xb5\x2f\xfd",
    "bzip2(BZh)": b"BZh", "LZ4LEGACY(02 21 4C 18)": b"\x02\x21\x4c\x18",
}
for name, m in MAGIC.items():
    print("  %-24s 在 GT7868Q主体 %2d 次  在 TF100A %2d 次" % (
        name, GQ.count(m), TF.count(m)))
print()
for name, fn in (("zlib", lambda b: zlib.decompress(b)),
                 ("lzma", lambda b: lzma.decompress(b))):
    ok = 0
    for off in range(0, 0x2000, 0x40):
        try:
            out = fn(GQ[off:])
            ok += 1
            print("  %s 从 +0x%04X 解压成功！输出 %d B 熵 %.4f" % (name, off, len(out), ent(out)))
            break
        except Exception:
            pass
    if not ok:
        print("  %s：所有尝试位置均失败（不是该格式）" % name)
print()

print("=" * 94)
print("H2 关键字节的位置分布（聚集 ⇒ 数据结构；分散 ⇒ 噪声）")
print("=" * 94)
for val in (0xB4, 0x5A, 0xB5, 0xB6, 0xCA):
    pos = [i for i, x in enumerate(GQ) if x == val]
    if not pos:
        print("  0x%02X : 0 次" % val)
        continue
    # 按 4 KiB 分桶
    buckets = collections.Counter(p // 0x1000 for p in pos)
    top = sorted(buckets.items(), key=lambda kv: -kv[1])[:5]
    print("  0x%02X : %3d 次，集中在 4KiB 桶 %s" % (
        val, len(pos), ", ".join("0x%05X×%d" % (0x1200 + b * 0x1000, c) for b, c in top)))
print()

print("=" * 94)
print("H3 跨段同源：GT7868Q 主体里有没有 TF100A 的元素？")
print("=" * 94)
for label, pat in (("外设基址 0x40010800", (0x40010800).to_bytes(4, "little")),
                   ("SRAM 0x20003F70", (0x20003F70).to_bytes(4, "little")),
                   ("字符串 TF100A", b"TF100A"),
                   ("字符串 Test_FW", b"Test_FW"),
                   ("十六进制表 abcdef", b"0123456789abcdef")):
    print("  %-24s GT7868Q主体 %d 次" % (label, GQ.count(pat)))
print()

print("=" * 94)
print("H4 标识串搜索（GT7868Q 主体 + 头部）")
print("=" * 94)
for pat in (b"GT7868", b"7868Q", b"Goodix", b"GOODIX", b"goodix", b"YELS",
            b"GXTP", b"5100", b"TEST", b"Test", b"Firmware", b"FW_"):
    print("  %-12s GT7868Q主体 %2d 次   头部 %2d 次   TF100A %2d 次" % (
        pat.decode("latin-1"), GQ.count(pat), d[:0x1200].count(pat), TF.count(pat)))
print()

print("=" * 94)
print("H5 GT7868Q 主体的「128 字节块」熵谱（若为定长记录，各块熵应相近）")
print("=" * 94)
R = 128
es = [ent(GQ[i:i + R]) for i in range(0, len(GQ) - R, R)]
print("  块数 %d  熵 min %.3f  max %.3f  均值 %.3f  标准差 %.3f" % (
    len(es), min(es), max(es), sum(es) / len(es),
    (sum((x - sum(es) / len(es)) ** 2 for x in es) / len(es)) ** 0.5))
print()
print("  对 TF100A 同测：")
es2 = [ent(TF[i:i + R]) for i in range(0, len(TF) - R, R)]
print("  块数 %d  熵 min %.3f  max %.3f  均值 %.3f  标准差 %.3f" % (
    len(es2), min(es2), max(es2), sum(es2) / len(es2),
    (sum((x - sum(es2) / len(es2)) ** 2 for x in es2) / len(es2)) ** 0.5))
