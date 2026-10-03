# parse_press.py —— 从原始报文里找"按下"位与压力字段，测定固件阈值
import re
import struct
from collections import Counter

LOG = r"<LAB>\touchpad-lab\poc\press-log.txt"
reports = []
for line in open(LOG, encoding="utf-8", errors="replace"):
    m = re.match(r"^RPT .*?len=(\d+) cnt=(\d+) data= (.*)$", line.strip())
    if m:
        ln = int(m.group(1))
        b = bytes.fromhex(m.group(3).replace(" ", ""))
        reports.append((ln, int(m.group(2)), b))
print(f"报文数: {len(reports)}  长度分布: {Counter(r[0] for r in reports)}")
if not reports:
    raise SystemExit("无报文")

n = min(len(r[2]) for r in reports)
print(f"最小长度 {n} 字节; 首条: {reports[0][2][:16].hex(' ')}")

# 1) 找出"翻转次数最多的位"（按下/抬起 5 次 -> 约 10 次跳变）
print("\n=== 各位的跳变次数 (Top 12) ===")
bit_trans = []
for bit in range(n * 8):
    tr = 0
    prev = None
    for _, _, b in reports:
        v = (b[bit // 8] >> (bit % 8)) & 1
        if prev is not None and v != prev:
            tr += 1
        prev = v
    bit_trans.append((tr, bit))
bit_trans.sort(reverse=True)
for tr, bit in bit_trans[:12]:
    print(f"  bit {bit:3d} (byte {bit//8:2d} bit{bit%8}) 跳变 {tr} 次")
tip_bit = bit_trans[0][1] if bit_trans and bit_trans[0][0] >= 4 else None
print(f"  选定的按键位: byte {tip_bit//8} bit{tip_bit%8}" if tip_bit is not None else "  未找到明显按键位")

# 2) 找压力字段：16 位小端，取值随按下上升、最大接近 2000
print("\n=== 16 位小端字段的统计 (找压力: 0~2000 且变化大) ===")
cands = []
for off in range(0, n - 1):
    vals = [struct.unpack_from("<H", b, off)[0] for _, _, b in reports]
    mx, mn = max(vals), min(vals)
    if 200 <= mx <= 2500 and mx - mn > 100:
        cands.append((mx - mn, off, mx, mn))
cands.sort(reverse=True)
for span, off, mx, mn in cands[:10]:
    print(f"  offset {off:2d}: max={mx:5d} min={mn:5d} 变化={span}")
press_off = cands[0][1] if cands else None

# 3) 按下瞬间的压力值 = 阈值
if tip_bit is not None and press_off is not None:
    print(f"\n=== 按下/抬起时刻的压力 (按键位=byte{tip_bit//8}.bit{tip_bit%8}, 压力@offset {press_off}) ===")
    prev = None
    rises = []
    for i, (_, cnt, b) in enumerate(reports):
        v = (b[tip_bit // 8] >> (tip_bit % 8)) & 1
        p = struct.unpack_from("<H", b, press_off)[0]
        x = struct.unpack_from("<H", b, 4)[0]
        y = struct.unpack_from("<H", b, 6)[0]
        if prev is not None and v != prev:
            kind = "按下" if v == 1 else "抬起"
            print(f"  [{i:3d}] {kind}  压力={p:5d}  X={x:4d} Y={y:4d}  cnt={cnt}")
            if v == 1:
                rises.append(p)
        prev = v
    print(f"\n  按下时刻的压力值: {rises}")
    if rises:
        print(f"  => 阈值估计: 最小 {min(rises)} / 最大 {max(rises)} / 中位 {sorted(rises)[len(rises)//2]}")

# 4) 打印压力随时间的变化（只看第一个触点，压缩显示）
if press_off is not None:
    print("\n=== 压力时间线 (每 10 条取 1) ===")
    seq = [struct.unpack_from("<H", b, press_off)[0] for _, _, b in reports]
    print("  " + " ".join(str(v) for v in seq[::10][:60]))
