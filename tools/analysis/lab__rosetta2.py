# rosetta2.py —— 画出明文配置(记录0-4)在传感器64KB空间中的完整布局
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

print("=== 记录 0-4 的每 64 字节块在传感器空间中的落点 ===")
for i in range(5):
    r = data[i * REC:(i + 1) * REC]
    print(f"\n--- 记录 {i} ---")
    for off in range(0, REC, 64):
        chunk = r[off:off + 64]
        if len(set(chunk)) <= 1:
            continue
        # 用 24 字节锚点
        anchor = chunk[:24]
        hits = []
        s = 0
        while True:
            j = mem.find(anchor, s)
            if j < 0:
                break
            hits.append(j)
            s = j + 1
        if hits:
            print(f"  记录+0x{off:03X} -> 转储 {[hex(h) for h in hits[:4]]}")
        else:
            # 试更短锚点
            anchor2 = chunk[:12]
            hits2 = []
            s = 0
            while True:
                j = mem.find(anchor2, s)
                if j < 0:
                    break
                hits2.append(j)
                s = j + 1
            if hits2:
                print(f"  记录+0x{off:03X} -> (12B锚点) {[hex(h) for h in hits2[:4]]}")
            else:
                print(f"  记录+0x{off:03X} -> 未命中")

print("\n=== 转储中的配置块范围 (以记录1首字节为锚，看连续匹配长度) ===")
r1 = data[1 * REC:2 * REC]
anchor = r1[:16]
pos = mem.find(anchor)
print(f"  记录1 起点匹配于转储 0x{pos:04X}; 连续一致长度检测:")
if pos >= 0:
    n = 0
    while pos + n < 0x10000 and n < len(r1) and mem[pos + n] == r1[n]:
        n += 1
    print(f"    连续一致 {n} 字节")
    # 打印该处前后各 32 字节
    s = max(0, pos - 32)
    for k in range(s, min(0x10000, pos + 96), 16):
        mark = " <== 记录1 起点" if k <= pos < k + 16 else ""
        print(f"    0x{k:04X}: {' '.join(f'{b:02X}' for b in mem[k:k+16])}{mark}")

print("\n=== 转储里 0x5E00 附近与记录1 的逐字节对照 (前 160 字节) ===")
pos = 0x5E06
for k in range(0, 160, 16):
    a = mem[pos + k:pos + k + 16]
    b = r1[k:k + 16]
    ok = "一致" if a == b else "不同"
    print(f"  +0x{k:03X} [{ok}] 转储 {' '.join(f'{x:02X}' for x in a)}")
    if a != b:
        print(f"           记录 {' '.join(f'{x:02X}' for x in b)}")
print("\n=== 记录1 中疑似阈值的 16 位小端值 (前 48 个) ===")
vals = [struct.unpack_from("<H", r1, k)[0] for k in range(0, 96, 2)]
print("  " + " ".join(f"{v:5d}" for v in vals))
