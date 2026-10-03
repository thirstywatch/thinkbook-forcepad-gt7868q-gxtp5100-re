# -*- coding: utf-8 -*-
"""8051 向量表检测器 v2 —— 加【孤立性】过滤（真向量表一张图只有一处，不会每 8 字节一条）"""
import os, collections

DET = (0x00, 0x03, 0x0B, 0x13, 0x1B, 0x23)

def scan(path):
    b = open(path, 'rb').read()
    n = len(b) - 0x30
    raw = []
    for o in range(n):
        s = 0
        for d in DET:
            if b[o + d] in (0x02, 0x12):
                s += 1
        if s >= 4:
            raw.append((o, s))
    h5 = [h for h in raw if h[1] >= 5]
    h4 = [h for h in raw if h[1] == 4]
    # 孤立性：与最近的其他命中相距 > 0x40 才算"孤立"
    def isolated(hs):
        out = []
        for i, (o, s) in enumerate(hs):
            prev_ok = (i == 0) or (o - hs[i - 1][0] > 0x40)
            next_ok = (i == len(hs) - 1) or (hs[i + 1][0] - o > 0x40)
            if prev_ok and next_ok:
                out.append((o, s))
        return out
    allh = sorted(raw)
    iso5 = isolated([h for h in allh if h[1] >= 5])
    iso4 = isolated([h for h in allh if h[1] == 4])
    return b, sz(b), h5, h4, iso5, iso4

def sz(b):
    return len(b)

FILES = [
    r"<LAB>\touchpad-lab\bios-re\GT7868Q_native_fw.bin",
    r"<LAB>\touchpad-lab\poc\decrypt-v2\GT7868Q_2024_本机_plain_data.bin",
    r"<LAB>\touchpad-lab\poc\decrypt-v2\GT7868Q_2020_Catalog_plain_data.bin",
    r"<LAB>\touchpad-lab\poc\decrypt-v2\GT9896_plain_data.bin",
    r"<LAB>\touchpad-lab\poc\decrypt-v2\GT7863_PNOR_G1_plain_data.bin",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
    r"<LAB>\touchpad-lab\vendor\goodix-lvfs\GT7936L_16753412.bin",
    r"<WORKSPACE>",
    r"<LAB>\touchpad-lab\bios-re\GoodixTpDxe.bin",
    r"<LAB>\touchpad-lab\bios-re\EcCapsuleDxe.bin",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
]
print("== 8051 向量表检测器 v2（含【孤立性】过滤）==")
print("%-52s %-10s %-7s %-7s %-9s %-9s %s" % ("文件", "大小", ">=5", "==4", "孤立>=5", "孤立==4", "最佳"))
print("-" * 118)
for p in FILES:
    if not os.path.exists(p):
        print("%-52s  <缺失>" % os.path.basename(p)); continue
    b, n, h5, h4, iso5, iso4 = scan(p)
    best = max(h5 + h4, key=lambda z: z[1]) if (h5 or h4) else None
    print("%-52s %-10d %-7d %-7d %-9d %-9d %s" % (
        os.path.basename(p), n, len(h5), len(h4), len(iso5), len(iso4),
        ("0x%X s=%d" % best) if best else "-"))
print("-" * 118)
print()
print("== 孤立命中明细（若真为 8051 向量表，这里应看到一条干净的 0x00/0x03/0x0B/0x13/0x1B/0x23 序列）==")
for p in FILES:
    if not os.path.exists(p): continue
    b, n, h5, h4, iso5, iso4 = scan(p)
    if iso5 or iso4:
        print("  " + os.path.basename(p))
        for o, s in (iso5 + iso4)[:6]:
            print("     @0x%X score=%d :: %s" % (o, s, " ".join("%02x" % c for c in b[o:o + 0x2C])))
