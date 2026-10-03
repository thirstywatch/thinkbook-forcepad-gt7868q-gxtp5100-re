# analyze_scan.py —— 分析 Goodix 16 位地址空间测绘结果
import re
import sys

SRC = r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"

mem = bytearray(b"\x00" * 0x10000)
covered = bytearray(0x10000)
fails = []
for line in open(SRC, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("done"):
        continue
    m = re.match(r"^0x([0-9A-F]{4})\s+(.*)$", line)
    if not m:
        continue
    addr = int(m.group(1), 16)
    rest = m.group(2)
    if rest.startswith("<FAIL"):
        fails.append((addr, rest))
        continue
    try:
        b = bytes.fromhex(rest)
    except ValueError:
        continue
    mem[addr:addr + len(b)] = b
    for i in range(addr, min(addr + len(b), 0x10000)):
        covered[i] = 1

print("失败读取:", len(fails))
print("覆盖字节:", sum(covered))

# 1) 非零区域图
print("\n=== 非零区域 (>=16 字节 非全零) ===")
runs = []
i = 0
while i < 0x10000:
    if mem[i] != 0:
        j = i
        while j < 0x10000 and any(mem[k] != 0 for k in range(j, min(j + 16, 0x10000))):
            j += 16
        runs.append((i, j))
        i = j
    else:
        i += 1
for a, b in runs:
    nz = sum(1 for k in range(a, b) if mem[k] != 0)
    print(f"  0x{a:04X} - 0x{b:04X}  ({b-a} 字节, 非零 {nz})")

# 2) ASCII 字符串
print("\n=== ASCII 字符串 (>=4 字符) ===")
for m in re.finditer(rb"[\x20-\x7E]{4,}", bytes(mem)):
    print(f"  0x{m.start():04X}: {m.group().decode('ascii')}")

# 3) 关键模式搜索
print("\n=== 关键模式 ===")
pats = {
    "HID 描述符头 05 0D 09 05": bytes.fromhex("050D0905"),
    "Haptics 用法页 06 0E 00 / 05 0E": None,
    "厂商用法页 06 00 FF": bytes.fromhex("0600FF"),
    "Goodix 字串": b"Goodix",
    "GT7868": b"7868",
    "普通 'STO' 片段": b"STO",
    "ARM 向量表特征 (SP 0x2000...)": None,
}
for name, pat in pats.items():
    if pat is None:
        continue
    hits = [m.start() for m in re.finditer(re.escape(pat), bytes(mem))]
    print(f"  {name}: {len(hits)} 处 {[hex(h) for h in hits[:10]]}")

for pat in (b"\x06\x0e\x00", b"\x05\x0e", b"\x09\x23"):
    hits = [m.start() for m in re.finditer(re.escape(pat), bytes(mem))]
    print(f"  {pat.hex(' ')}: {len(hits)} 处 {[hex(h) for h in hits[:10]]}")

# 4) 16 位小端值直方图，找"表"
print("\n=== 疑似表结构 (连续 16 位小端值, 前 8 个) ===")
for a, b in runs[:12]:
    vals = [int.from_bytes(mem[k:k + 2], "little") for k in range(a, min(a + 16, b), 2)]
    print(f"  0x{a:04X}: " + " ".join(f"{v:04X}" for v in vals))
