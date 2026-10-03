# analyze_scan2.py —— 深度分析：是否代码区 / 指针表 / 与 BIN 的关系
import re
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

SRC = r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"
BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"

mem = bytearray(0x10000)
for line in open(SRC, encoding="utf-8", errors="replace"):
    line = line.strip()
    m = re.match(r"^0x([0-9A-F]{4})\s+([0-9A-F ]+)$", line)
    if not m:
        continue
    a = int(m.group(1), 16)
    b = bytes.fromhex(m.group(2))
    mem[a:a + len(b)] = b

print("=== 原始区段 ===")
for start, ln in ((0x1000, 128), (0x4000, 96), (0x4100, 64)):
    print(f"\n0x{start:04X}:")
    for off in range(0, ln, 16):
        chunk = mem[start + off:start + off + 16]
        hexs = " ".join(f"{x:02X}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        print(f"  {start+off:04X}: {hexs}  {asc}")

print("\n=== 疑似入口/表：32 位小端值落在 MCU 地址区间 ===")
ranges = {
    "flash 0x08000000-0x08020000": (0x08000000, 0x08020000),
    "sram  0x20000000-0x20008000": (0x20000000, 0x20008000),
    "periph 0x40000000-0x40010000": (0x40000000, 0x40010000),
}
found = {k: [] for k in ranges}
for a in range(0, 0xFFFC):
    v = struct.unpack_from("<I", mem, a)[0]
    for k, (lo, hi) in ranges.items():
        if lo <= v < hi:
            found[k].append((a, v))
for k, lst in found.items():
    print(f"  {k}: {len(lst)} 处")
    for a, v in lst[:12]:
        print(f"     0x{a:04X} -> 0x{v:08X}")

print("\n=== Thumb 反汇编得分（看哪个区间是真代码）===")
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
for start in (0x1000, 0x2000, 0x4000, 0x4114, 0x5000, 0x6000, 0x7000, 0x8000,
              0x9000, 0x9BDB, 0xA000, 0xB000, 0xB82E, 0xC000):
    code = bytes(mem[start:start + 1024])
    total = 0
    bad = 0
    for ins in md.disasm(code, start):
        total += 1
        if ins.id == 0:
            bad += 1
    print(f"  0x{start:04X}: 指令 {total:4d} 未定义/跳字节 {bad:4d}  有效率 {(1-bad/total)*100 if total else 0:5.1f}%")

print("\n=== 与 BIN 的长锚点比对（在 BIN 中搜索内存片段）===")
data = open(BIN, "rb").read()
for start in (0x1000, 0x2000, 0x4000, 0x4114, 0x6000, 0x8000, 0x9BDB, 0xB000, 0xB100):
    w = bytes(mem[start:start + 48])
    if w.count(0) > 40:
        continue
    hits = []
    s = 0
    while True:
        i = data.find(w, s)
        if i < 0:
            break
        hits.append(i)
        s = i + 1
    tag = "命中" if hits else "未命中"
    print(f"  0x{start:04X} 48字节 -> {tag} {[hex(h) for h in hits[:4]]}")
