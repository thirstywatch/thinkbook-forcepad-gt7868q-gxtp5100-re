# -*- coding: utf-8 -*-
"""第四层：0x0800D400+ 区域到底是什么？——熵剖面 + 代码指针直方图 + 字符串锚点
若该区是"文件里的字节≠运行时该地址的字节"，熵和指针分布会露馅。
"""
import math, re, struct, bisect

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
full = open(BIN, 'rb').read()
data = full[OFF:OFF + LEN]
END = BASE + LEN


def ent(b):
    if not b:
        return 0.0
    c = [0] * 256
    for x in b:
        c[x] += 1
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c if v)


print("### A. 熵剖面（每 1KB）")
for k in range(0, LEN, 1024):
    h = ent(data[k:k + 1024])
    bar = '#' * int(h * 8)
    print(f"  {BASE+k:#010x}  H={h:4.2f}  {bar}")

print("\n\n### B. 代码指针字面量直方图（u32 ∈ [0x08000000,0x0800F000)，按 0x1000 页）")
hist = {}
stragglers = []
for k in range(0, LEN - 4):
    v = struct.unpack_from('<I', data, k)[0]
    if 0x08000000 <= v < 0x0800F000:
        page = v & 0xFFFFF000
        hist[page] = hist.get(page, 0) + 1
        if v >= 0x0800C000:
            stragglers.append((BASE + k, v))
for p in sorted(hist):
    print(f"  {p:#010x}: {hist[p]:4d}  {'#'*min(hist[p],60)}")
print(f"\n  ≥0x0800C000 的指针共 {len(stragglers)} 个：")
for a, v in stragglers:
    print(f"    @{a:#010x} → {v:#010x}")

print("\n\n### C. 字符串锚点")
for pat in (b'TF100A', b'Test_FW', b'5.21.01', b'Nov 28 2023', b'GT7868', b'GXTP'):
    for m in re.finditer(re.escape(pat), data):
        print(f"  {pat.decode()} @ {BASE+m.start():#010x} (文件 {OFF+m.start():#x})")

print("\n\n### D. 0x0800D619 周期性区段的真实范围")
i = 0x19ABC + (0x0800D619 - BASE)
run_start = None
runs = []
k = 0x19ABC
while k < 0x19ABC + LEN - 3:
    if full[k:k + 3] == b'\x54\x12\xa5':
        s = k
        while k < 0x19ABC + LEN - 3 and full[k:k + 3] == b'\x54\x12\xa5':
            k += 3
        runs.append((s, k))
    k += 1
print(f"  '5412a5' 三字节周期段共 {len(runs)} 段")
for s, e in runs[:20]:
    print(f"    {BASE+s-0x19ABC:#010x}..{BASE+e-0x19ABC:#010x}  ({(e-s)} 字节)")

print("\n\n### E. 镜像首尾字节")
print(f"  头 32 字节: {data[:32].hex(' ')}")
print(f"  尾 64 字节: {data[-64:].hex(' ')}")

print("\n\n### F. 0x0800C000–0x0800DCA0 每 256 字节熵")
for k in range(0x0800C000 - BASE, LEN, 256):
    h = ent(data[k:k + 256])
    print(f"  {BASE+k:#010x}  H={h:4.2f}  {'#'*int(h*8)}")
