# -*- coding: utf-8 -*-
"""R8-4 ★★★ 在本机容器/载荷里搜【HID 描述符本体】
 本机描述符真值（hid-dump.txt）: X LogicalMax=4149(0x1036→ 26 7F 0D? 注意 HID 是小端 16 位)
   HID 编码：26 7F 0D = Logical Max 0x0D7F = 3455（那是 wiki 的 7863）
   本机是 4149 = 0x1035...  hmm: 4149 = 0x1035 -> 26 35 10
   ⇒ 本机描述符里应是 26 35 10 (X) 与 26 63 08 (Y, 2147=0x0863)
  若这些字节出现在容器里 ⇒ 描述符本体在包内 ⇒ 能拿到 Physical Max 等第三个真值"""
import os

D = r"<WORKSPACE>"
SRC = {
    '本机容器(原)': open(rf"{D}\orig_TB14P.bin", 'rb').read(),
    '载荷A 解扰后': open(rf"{D}\A_2024.bin", 'rb').read(),
    '载荷A 原始': open(rf"{D}\orig_TB14P.bin", 'rb').read()[0x123C:0x123C + 100352],
    '载荷B(TF100A)': open(rf"{D}\orig_TB14P.bin", 'rb').read()[0x19A3C:0x2775C],
    'capA 容器': open(rf"{D}\cap22001E0D.Cap", 'rb').read(),
}

XMAX, YMAX = 4149, 2147
PATTERNS = {
    '本机 X LogicalMax (26 35 10)': bytes([0x26, XMAX & 0xFF, XMAX >> 8]),
    '本机 Y LogicalMax (26 63 08)': bytes([0x26, YMAX & 0xFF, YMAX >> 8]),
    'PTP 触控板集合头 (05 0D 09 05 A1 01)': bytes.fromhex('050d0905a101'),
    'Logical Collection (05 0D 09 22 A1 02)': bytes.fromhex('050d0922a102'),
    'Report ID 4 (85 04)': bytes.fromhex('8504'),
    'Report ID 14 (85 0E)': bytes.fromhex('850e'),
    '厂商 256B 特征 (85 06 09 C5 26 FF 00 75 08)': bytes.fromhex('850609C5150026FF007508'),
    'Haptics rid=9 (85 09 09 23)': bytes.fromhex('85090923'),
    'ContactID (09 51)': bytes.fromhex('0951'),
}

print("=" * 100)
print("### 1 在五份数据里搜描述符特征字节串")
print("=" * 100)
for nm, d in SRC.items():
    print(f"\n--- {nm} ({len(d)} B) ---")
    for tag, pat in PATTERNS.items():
        hits = []
        i = d.find(pat)
        while i >= 0 and len(hits) < 6:
            hits.append(i); i = d.find(pat, i + 1)
        if hits:
            print(f"    {tag:<44} 命中 {len(hits)}+ @ {[hex(h) for h in hits]}")

print("\n" + "=" * 100)
print("### 2 本机描述符的 Physical Max（从 hid-dump 无法直接得，改从容器里找 46 xx xx 序列）")
print("=" * 100)
raw = SRC['载荷A 解扰后']
cand = []
for i in range(len(raw) - 3):
    if raw[i] == 0x46 or raw[i] == 0x36:      # Physical Max (2B) / Physical Min
        v = raw[i+1] | (raw[i+2] << 8)
        if 50 <= v <= 3000:
            cand.append((i, raw[i], v))
print(f"  载荷A 解扰后里 46/36 后跟 50..3000 的位置: {len(cand)} 处（前 18）")
for i, op, v in cand[:18]:
    print(f"    +0x{i:05x}  op={op:02x} v={v}  上下文 {raw[max(0,i-6):i+8].hex(' ')}")

print("\n" + "=" * 100)
print("### 3 决定性：本机 cfg 里是否还有 'Physical Max + 1' 或 '= 4149/2147 的物理对应'")
print("=" * 100)
cfg = SRC['本机容器(原)'][0x4C:0x4C + 1024]
print(f"  cfg +0x100..+0x120: {cfg[0x100:0x120].hex(' ')}")
for p in range(0x0, 0x400, 2):
    be = int.from_bytes(cfg[p:p+2], 'big')
    le = int.from_bytes(cfg[p:p+2], 'little')
    if 3000 <= be <= 6000 or 1500 <= be <= 3000:
        pass
print("  --- cfg 里 3000..6000 与 1500..3000 的 u16BE（用于比对 Physical 值域）---")
for p in range(0, 0x400, 2):
    be = int.from_bytes(cfg[p:p+2], 'big')
    if 1500 <= be <= 6000:
        print(f"    +0x{p:03x}  u16BE {be}")
