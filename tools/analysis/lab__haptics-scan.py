#!/usr/bin/env python3
# haptics-scan.py —— 在固件/BIOS 里找「Haptics HID 描述符」的字节序列
#
# 关键判据：要「有扳机」（主机可触发），描述符里必须有
#   Usage Page (Haptics) = 05 0E
#   Usage (Manual Trigger) = 09 21  或  0A 21 00
#   Usage (Waveform List)  = 09 10  或  0A 10 00
#   Usage (Duration List)  = 09 11  或  0A 11 00
#   Usage (Simple Haptic Controller) = 09 01，通常紧跟 05 0E
#
# 统计纪律：n 字节模式在 N 字节文件里偶然命中期望 = N / 256^n
#   3 字节 → N/16.7M；4 字节 → N/4.3G。必须报出期望值，否则无意义。
import sys, os

FILES = [
    (r"<WORKSPACE>", "Goodix UEFI DXE 驱动"),
    (r"<WORKSPACE>", "EC SMM 驱动"),
    (r"<WORKSPACE>", "EC Capsule DXE"),
    (r"<WORKSPACE>", "完整 BIOS 16MB"),
    (r"<WORKSPACE>", "BIOS 解压体 30MB"),
    (r"<WORKSPACE>", "GT7868Q 容器"),
    (r"<WORKSPACE>", "GT7936L 固件(BERLIN)"),
]

# 长度 >=4 的模式才有统计力
PATTERNS = [
    ("05 0E 09 01 A1 02", bytes([0x05,0x0E,0x09,0x01,0xA1,0x02]), "★ SimpleHapticController 集合开头"),
    ("05 0E 09 21",       bytes([0x05,0x0E,0x09,0x21]),             "★ Haptics页 + Manual Trigger"),
    ("05 0E 0A 21 00",    bytes([0x05,0x0E,0x0A,0x21,0x00]),       "★ Haptics页 + Manual Trigger(2字节形式)"),
    ("05 0E 09 23",       bytes([0x05,0x0E,0x09,0x23]),             "Haptics页 + Intensity"),
    ("05 0E 09 10",       bytes([0x05,0x0E,0x09,0x10]),             "Haptics页 + Waveform List"),
    ("05 0E 09 11",       bytes([0x05,0x0E,0x09,0x11]),             "Haptics页 + Duration List"),
    ("09 21 75 08 95 01 91 02", bytes([0x09,0x21,0x75,0x08,0x95,0x01,0x91,0x02]), "★ Manual Trigger 作为 OUTPUT 报表(8字节)"),
    ("09 23 85 09",       bytes([0x09,0x23,0x85,0x09]),             "Intensity + RID 9（本机那一条的形态）"),
    ("05 0E 09 01 A1 02 09 23", bytes([0x05,0x0E,0x09,0x01,0xA1,0x02,0x09,0x23]), "★ 完整：Haptics集合+Intensity(8字节)"),
]

def scan(path, label, ctx=48, maxdump=2):
    print("=" * 78)
    if not os.path.exists(path):
        print(f"{label}\n  ✗ 文件不存在: {path}")
        return
    data = open(path, "rb").read()
    N = len(data)
    print(f"{label}   ({N:,} 字节)\n  {path}")
    for name, pat, desc in PATTERNS:
        n = data.count(pat)
        exp = N / (256 ** len(pat))
        flag = ""
        if n and exp < 0.01: flag = "  ★★★ 远超偶然（有统计意义）"
        elif n and exp < 0.5: flag = "  ★ 可能非偶然"
        elif n: flag = "  （在偶然范围内，无意义）"
        print(f"  {name:<28} n={n:<5} 偶然期望={exp:8.3f}{flag}   {desc}")
        if n and exp < 0.5:
            idx = 0; shown = 0
            while shown < maxdump:
                i = data.find(pat, idx)
                if i < 0: break
                lo = max(0, i - ctx // 2); hi = min(N, i + ctx // 2)
                print(f"      @0x{i:X}: {' '.join('%02X' % b for b in data[lo:hi])}")
                idx = i + 1; shown += 1
    print()

for p, l in FILES:
    scan(p, l)
print("done")
