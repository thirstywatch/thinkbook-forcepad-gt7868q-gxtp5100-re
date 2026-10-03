"""扫全部 ACPI 表：统计 I2C 从机资源描述符与可疑 ASCII 串。
目的：看主机这条 I2C0 总线上 ACPI 一共描述了几个从机。
"""
import glob, os, re, collections

D = r"<WORKSPACE>"
files = sorted(glob.glob(os.path.join(D, "*.bin")))
print("ACPI 文件数:", len(files))

pat = re.compile(rb"I2cSerialBus(?:V2)?")
total = collections.Counter()
addr_hits = []
for f in files:
    b = open(f, "rb").read()
    for m in pat.finditer(b):
        tag = m.group(0).decode()
        total[tag] += 1
        # 描述符: 8E xx xx 00 01 01 00 <type> <flags> <u16 rev> <u16 addr> <u32 speed> ...
        # 在 tag 之后若干字节里找从机地址
        seg = b[m.start():m.start() + 40]
        addr_hits.append((os.path.basename(f), tag, m.start(), " ".join("%02X" % c for c in seg[:24])))

print("I2cSerialBus 描述符出现次数:", dict(total))
print("\n逐条（文件 / 类型 / 偏移 / 之后 24 字节）：")
for f, tag, off, hexs in addr_hits[:40]:
    print("  %-34s %-14s @0x%06X  %s" % (f, tag, off, hexs))

# 可疑串
KEYS = [b"haptic", b"Haptic", b"vibrat", b"Vibrat", b"LRA", b"motor", b"Motor",
        b"TRIG", b"trigger", b"CA4F", b"AW86927", b"Goodix", b"GXTP", b"TF100A",
        b"Titan", b"Nidec", b"I2C0", b"I2C1", b"0x2C"]
print("\n=== 可疑 ASCII 串命中 ===")
for f in files:
    b = open(f, "rb").read()
    hits = [k.decode() for k in KEYS if k in b]
    if hits:
        print("  %-34s %s" % (os.path.basename(f), ", ".join(hits)))
