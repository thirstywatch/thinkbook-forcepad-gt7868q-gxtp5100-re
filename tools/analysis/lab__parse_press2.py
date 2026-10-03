# parse_press2.py —— 正确布局下的压力/阈值解析
import re
import struct

LOG = r"<LAB>\touchpad-lab\poc\press-log.txt"
reports = []
for line in open(LOG, encoding="utf-8", errors="replace"):
    m = re.match(r"^RPT .*?len=(\d+) cnt=(\d+) data= (.*)$", line.strip())
    if m:
        reports.append((int(m.group(2)), bytes.fromhex(m.group(3).replace(" ", ""))))
print(f"报文数: {len(reports)}")

# 按键位 = byte1 bit0；触点在 byte1 高 4 位
trans = []
prev = None
for i, (cnt, b) in enumerate(reports):
    v = b[1] & 1
    if prev is not None and v != prev:
        trans.append((i, v))
    prev = v
print(f"按键位跳变 {len(trans)} 次: {trans[:14]}")

print("\n=== 所有 16 位小端字段的取值统计 ===")
for off in range(0, 39, 2):
    vals = [struct.unpack_from("<H", b, off)[0] for _, b in reports]
    mx, mn = max(vals), min(vals)
    print(f"  off={off:2d}: min={mn:5d} max={mx:5d} 变化={mx-mn:5d}")

print("\n=== 每个'按下'瞬间各字段的值 (找哪个字段在按下时跳变) ===")
prev = None
for i, (cnt, b) in enumerate(reports):
    v = b[1] & 1
    if prev is not None and v != prev:
        kind = "按下" if v == 1 else "抬起"
        vals = [struct.unpack_from("<H", b, o)[0] for o in range(2, 20, 2)]
        print(f"  [{i:3d}] {kind} cnt={cnt} b1=0x{b[1]:02X} 字段(off2..18)=" + " ".join(f"{x}" for x in vals))
    prev = v

print("\n=== 压力时间线 (off=6 与 off=12 对照, 每 5 条) ===")
for off in (6, 12, 18):
    seq = [struct.unpack_from("<H", b, off)[0] for _, b in reports]
    print(f"  off={off:2d}: " + " ".join(f"{v}" for v in seq[::5][:40]))
print("\n=== 按键位时间线 (每 5 条) ===")
seq = [(b[1] & 1) for _, b in reports]
print("  " + "".join(str(v) for v in seq[::5][:80]))
