# rosetta.py —— 用明文配置记录(0-4)去匹配传感器 64KB 转储，定位配置寄存器
import re
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
DUMP = r"<LAB>\touchpad-lab\poc\mem-scan-16bit.txt"
REC = 1084

data = open(BIN, "rb").read()
mem = bytearray(0x10000)
for line in open(DUMP, encoding="utf-8", errors="replace"):
    m = re.match(r"^0x([0-9A-F]{4})\s+([0-9A-F ]+)$", line.strip())
    if m:
        a = int(m.group(1), 16)
        b = bytes.fromhex(m.group(2))
        mem[a:a + len(b)] = b

print("=== A) 明文配置记录的原始字节 (记录 0-4) ===")
for i in range(5):
    r = data[i * REC:(i + 1) * REC]
    print(f"\n记录{i} (熵={len(set(r))} 唯一字节, 前 96 字节):")
    for k in range(0, 96, 16):
        print(f"   {k:04X}: {' '.join(f'{b:02X}' for b in r[k:k+16])}")

print("\n=== B) 用记录 0-4 的窗口搜索传感器转储 (精确 / 反序) ===")
hits_total = 0
for i in range(5):
    r = data[i * REC:(i + 1) * REC]
    found = []
    for wlen in (16, 8, 6, 4):
        for off in range(0, len(r) - wlen, 2):
            w = r[off:off + wlen]
            if len(set(w)) <= 2:      # 跳过过于平凡（如全 0/全同）的窗口
                continue
            j = mem.find(w)
            if j >= 0:
                found.append((wlen, off, j, w.hex(' ')))
        if found:
            break
    print(f"  记录{i}: 命中 {len(found)} 处" + ("" if not found else ""))
    for wlen, off, j, hx in found[:8]:
        print(f"     {wlen}B @记录+0x{off:03X}  ->  转储 0x{j:04X}   [{hx}]")
    hits_total += len(found)
print(f"\n  合计命中 {hits_total} 处")

print("\n=== C) 记录 0-4 里的 16 位小端值统计 (找阈值候选) ===")
for i in range(5):
    r = data[i * REC:(i + 1) * REC]
    vals = [struct.unpack_from("<H", r, k)[0] for k in range(0, 64, 2)]
    print(f"  记录{i} 前 32 个 16 位值: " + " ".join(f"{v:5d}" for v in vals))
