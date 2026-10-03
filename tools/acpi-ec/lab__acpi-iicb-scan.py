#!/usr/bin/env python3
# acpi-iicb-scan.py —— 查 IICB / ADR0 / I2C0 的定义与引用，定位 TPAD 的 I2C 地址来源
#
# 背景：DSDT 的 TPAD 子树里 _DSM 用 ConcatRes(<8字节名>, ...) 拼资源描述符。
#       该 8 字节名在 AML 里是【裸写无 DualNamePrefix】，标准读法应拆成 IICB + ADR0 两个 NameSeg。
#       ADR0 在 TPAD 里有 Name(ADR0, Zero)。真正未解的是 IICB。
# 本脚本：找出 IICB 的独立出现（非 IICBADR0 组成部分），以及 SSDO 里 I2C0 的上下文。
import os, glob, re

ROOT = r"<WORKSPACE>"

def files():
    out = []
    for pat in ("acpi-dump/*.bin", "bios/out/*.bin", "bios/extract/*.bin"):
        out += glob.glob(os.path.join(ROOT, pat))
    return [f for f in out if os.path.getsize(f) > 500]

def scan(name, b, skip_if_followed_by=None):
    nb = name.encode('ascii')
    res = []
    i = 0
    while True:
        i = b.find(nb, i)
        if i < 0:
            break
        tag = ""
        if skip_if_followed_by is not None:
            tail = b[i+len(nb): i+len(nb)+len(skip_if_followed_by)]
            if tail == skip_if_followed_by:
                tag = "(内含)"
        res.append((i, tag))
        i += 1
    return res

print("=" * 78)
print("A) 各 4 字节名在 ACPI/BIOS 表里的出现")
print("=" * 78)
targets = {
    "IICB": "ADR0",   # 若后面紧跟 ADR0 则属 IICBADR0
    "ADR0": None,
    "IIC1": "ADR1",
    "ADR1": None,
    "IIC0": "ADR0",
    "I2C0": None,
    "GXTP": None,
}
fs = files()
print(f"扫描 {len(fs)} 个文件\n")
for name, follow in targets.items():
    rows = []
    nb = name.encode()
    for f in fs:
        b = open(f, "rb").read()
        hits = scan(name, b, follow.encode() if follow else None)
        if hits:
            indep = [h for h in hits if h[1] != "(内含)"]
            rows.append((os.path.basename(f), len(hits), len(indep),
                         " ".join(f"0x{h[0]:X}{h[1]}" for h in hits[:8])))
    if not rows:
        print(f"  {name:6} -> 0")
        continue
    print(f"  {name:6}")
    for fn, tot, ind, det in rows:
        print(f"      {fn:46} 共{tot:3d}  独立{ind:3d}   {det}")

print()
print("=" * 78)
print("B) SSDO 里 I2C0 附近 96 字节（判断是否 I2C0 Device 定义 / 是否含地址表）")
print("=" * 78)
ssdo = glob.glob(os.path.join(ROOT, "acpi-dump", "SSDO*.bin"))
if not ssdo:
    print("  未找到 SSDO")
else:
    b = open(ssdo[0], "rb").read()
    print(f"  文件: {os.path.basename(ssdo[0])}  {len(b)} B")
    i = 0
    n = 0
    while n < 4:
        i = b.find(b"I2C0", i)
        if i < 0:
            break
        print(f"\n  --- I2C0 @0x{i:X} ---")
        lo = max(0, i - 48)
        hi = min(len(b), i + 64)
        for o in range(lo, hi, 16):
            seg = b[o:o+16]
            txt = "".join(chr(x) if 32 <= x < 127 else "." for x in seg)
            print(f"     0x{o:05X}: " + " ".join(f"{x:02X}" for x in seg) + "  " + txt)
        i += 1
        n += 1

print()
print("=" * 78)
print("C) 哪张表定义了 TPAD 用到的 I2C 控制器（搜 IIC0/IIC1 方法名与 _ADR/_HID）")
print("=" * 78)
for f in fs:
    b = open(f, "rb").read()
    if b.find(b"I2C0") >= 0 or b.find(b"IIC0") >= 0:
        print(f"  {os.path.basename(f):46} {len(b):8} B   I2C0@{b.find(b'I2C0')}  IIC0@{b.find(b'IIC0')}")
