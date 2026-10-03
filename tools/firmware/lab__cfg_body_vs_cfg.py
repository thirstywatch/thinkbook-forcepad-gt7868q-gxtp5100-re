# -*- coding: utf-8 -*-
"""1024 B 配置体 vs tpcfgsid*.cfg —— 跨文件逐字节比对（排除平凡片段）"""
import os, collections, struct
d = open("bios-re/GT7868Q_native_fw.bin", 'rb').read()
BODY = d[0x4C:0x4C + 1024]
TAIL = d[0x4C + 1024:0x4C + 1084]
CFG = {
    "sid0(Xiaomi7867)": "<WORKSPACE>",
    "sid2": "<WORKSPACE>",
    "sid3(LaiBao7986P)": "<WORKSPACE>",
}
def trivial(s):
    return len(set(s)) <= 2      # 全 0 / 全 FF / 两个值以内 → 平凡
def runs(a, b, minlen=6):
    res = []; i = 0
    while i < len(a) - minlen:
        best = (0, -1)
        for j in range(len(b) - minlen + 1):
            L = 0
            while i + L < len(a) and j + L < len(b) and a[i + L] == b[j + L]:
                L += 1
            if L > best[0]: best = (L, j)
        if best[0] >= minlen:
            res.append((i, best[1], best[0])); i += best[0]
        else: i += 1
    return res

for nm, p in CFG.items():
    if not os.path.exists(p): continue
    cb = open(p, 'rb').read()
    print("=" * 90)
    print("### 配置体(1024B) ↔ %s (%d B)" % (nm, len(cb)))
    for label, X in [("配置体", BODY), ("60B尾", TAIL)]:
        rs = runs(X, cb, 6)
        real = [(o, j, L) for (o, j, L) in rs if not trivial(X[o:o + L])]
        print("  %s: 公共片段 %d 段（其中非平凡 %d 段）" % (label, len(rs), len(real)))
        for o, j, L in real[:12]:
            print("    体+0x%03X ↔ cfg+0x%03X 长 %3d : %s" % (o, j, L, X[o:o + min(L, 32)].hex(' ')))
    # 反向：cfg 的内容片段是否出现在配置体
    rs2 = runs(cb, BODY, 8)
    real2 = [(o, j, L) for (o, j, L) in rs2 if not trivial(cb[o:o + L])]
    print("  cfg → 配置体：非平凡公共片段 %d 段" % len(real2))
    for o, j, L in real2[:10]:
        print("    cfg+0x%03X ↔ 体+0x%03X 长 %3d : %s" % (o, j, L, cb[o:o + min(L, 32)].hex(' ')))

print()
print("=" * 90)
print("### 追加三十六 记的「跨厂商 54 B 骨架」是否出现在配置体里")
print("### 骨架特征串（时长/系数阶梯）: 10,20,80,800,1000,2000,8000,10000,600,45,400,0,5000,0,10000,0")
SEQ = [10, 20, 80, 800, 1000, 2000, 8000, 10000, 600, 45, 400, 0, 5000, 0, 10000, 0]
for name, fmt in [("u16 LE", "<H"), ("u16 BE", ">H")]:
    pat = b"".join(struct.pack(fmt, v) for v in SEQ)
    print("  %s 整串: %s  → 配置体命中 %d 处 ; 60B尾命中 %d 处"
          % (name, pat.hex(' '), BODY.count(pat), TAIL.count(pat)))
# 宽松：只查前 8 个值的序列
for n in (4, 6, 8, 10):
    pat = b"".join(struct.pack("<H", v) for v in SEQ[:n])
    pb = b"".join(struct.pack(">H", v) for v in SEQ[:n])
    print("  前%2d 个值: LE 命中 %d/%d（体/尾）  BE 命中 %d/%d"
          % (n, BODY.count(pat), TAIL.count(pat), BODY.count(pb), TAIL.count(pb)))

print()
print("=" * 90)
print("### 配置体里所有「非平凡」的 u16 长平台（≥8 个相同值）")
for name, fmt, w in [("LE", "<", 2), ("BE", ">", 2)]:
    vals = [int.from_bytes(BODY[j:j+2], fmt) for j in range(0, 1022, 2)]
    i = 0
    print("  %s:" % name)
    while i < len(vals):
        v = vals[i]; j = i
        while j < len(vals) and vals[j] == v: j += 1
        if j - i >= 8 and v not in (0, 0xFFFF):
            print("    体+0x%03X  %3d 个 × %5d (0x%04X)" % (i * 2, j - i, v, v))
        i = j
