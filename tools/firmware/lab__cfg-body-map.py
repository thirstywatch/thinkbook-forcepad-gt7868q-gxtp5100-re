# -*- coding: utf-8 -*-
"""任务 1+2：配置体(1024 B) 的离线结构解析 + 与 tpcfgsid*.cfg 的 TAG 0x01 索引表对齐
   产物：分段地图 + 索引表对齐结果"""
import os, struct, collections

LAB = r"<LAB>\touchpad-lab"
CFG = r"<WORKSPACE>"
d = open(os.path.join(LAB, "bios-re", "GT7868Q_native_fw.bin"), 'rb').read()
BODY = d[0x4C:0x4C + 1024]
TAIL = d[0x4C + 1024:0x4C + 1084]

def walk(buf, st=0x40):
    i = st; out = []
    while i + 2 <= len(buf):
        ln = buf[i]; tag = buf[i + 1]
        if ln < 2 or i + ln > len(buf):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, buf[i + 2:i + ln])); i += ln
    return out

S = {nm: open(os.path.join(CFG, nm + ".bin"), 'rb').read() for nm in ("sid0", "sid3")}
W = {nm: {x[1]: (x[0], x[2], x[3]) for x in walk(S[nm]) if x[3] is not None} for nm in S}

print("=" * 100)
print("### 1. 配置体逐字节地图（1024 B，16 B/行，右侧标注）")
print("=" * 100)

def annot(off, b):
    return ""

for i in range(0, 1024, 16):
    row = BODY[i:i + 16]
    hx = " ".join("%02x" % c for c in row)
    asc = "".join(chr(c) if 32 <= c < 127 else '.' for c in row)
    # 行特征
    feats = []
    if len(set(row)) == 1:
        feats.append("常量0x%02X" % row[0])
    else:
        if all(row[k] <= row[k + 1] for k in range(len(row) - 1)) and row[-1] <= 0x80:
            feats.append("递增")
        # u16 LE 全部 < 0x100 且非零
        v = [struct.unpack_from('<H', row, k)[0] for k in range(0, len(row) - 1, 2)]
        if all(0x7000 <= x <= 0x8000 for x in v):
            feats.append("u16BE≈0x7xxx")
        elif all(0 <= x <= 0x400 for x in v) and any(x >= 8 for x in v):
            feats.append("u16LE小值 max=%d" % max(v))
    print("  +0x%03X  %-47s  |%-16s|  %s" % (i, hx, asc, " ".join(feats)))

print()
print("=" * 100)
print("### 2. 自动分段（连续特征段）")
print("=" * 100)
segs = []
i = 0
while i < 1024:
    b = BODY[i]
    # 常量段
    j = i
    while j < 1024 and BODY[j] == b:
        j += 1
    if j - i >= 4:
        segs.append((i, j - i, "常量0x%02X" % b)); i = j; continue
    # 递增段
    j = i + 1
    while j < 1024 and BODY[j] == BODY[j - 1] + 1:
        j += 1
    if j - i >= 4:
        segs.append((i, j - i, "递增索引 %02X..%02X" % (BODY[i], BODY[j - 1]))); i = j; continue
    # u16BE ≈0x7xxx 段
    j = i; ok = True; n = 0
    while j + 1 < 1024 and 0x7000 <= struct.unpack_from('>H', BODY, j)[0] <= 0x8000:
        j += 2; n += 1
    if n >= 3:
        segs.append((i, j - i, "u16BE×%d（0x76xx-0x7Fxx）" % n)); i = j; continue
    # u16LE 小值段
    j = i; n = 0; mx = 0
    while j + 1 < 1024:
        x = struct.unpack_from('<H', BODY, j)[0]
        if x <= 0x800:
            j += 2; n += 1; mx = max(mx, x)
        else:
            break
    if n >= 3:
        segs.append((i, j - i, "u16LE×%d max=%d" % (n, mx))); i = j; continue
    i += 1

for a, l, t in segs:
    print("  +0x%03X  len=%-4d  %s" % (a, l, t))

print()
print("=" * 100)
print("### 3. TAG 0x01（通道/节点索引表）的内部结构 —— sid0 / sid3")
print("=" * 100)
for nm in ("sid0", "sid3"):
    off, ln, pl = W[nm][0x01]
    print("  %s  TAG 0x01  载荷 %d B（条目头 @0x%03X）" % (nm, len(pl), off))
    for k in range(0, len(pl), 16):
        print("     +%03X  %-47s  |%s|" % (k, " ".join("%02x" % c for c in pl[k:k + 16]),
              "".join(chr(c) if 32 <= c < 127 else '.' for c in pl[k:k + 16])))

print()
print("=" * 100)
print("### 4. 配置体里的索引片段 ↔ sid0/sid3 的 TAG 0x01 载荷：逐段对齐")
print("=" * 100)
idxsegs = [(a, l, t) for a, l, t in segs if t.startswith("递增")]
for a, l, t in idxsegs:
    frag = BODY[a:a + l]
    for nm in ("sid0", "sid3"):
        off, ln, pl = W[nm][0x01]
        k = pl.find(frag)
        if k >= 0:
            print("  体 +0x%03X (%dB %s)  →  %s TAG0x01 载荷 +%d  ✓" % (a, l, t, nm, k))
        else:
            k = S[nm].find(frag)
            print("  体 +0x%03X (%dB %s)  →  %s 全文件 %s" % (a, l, t, nm, ("@0x%03X" % k) if k >= 0 else "✗ 无"))

print()
print("=" * 100)
print("### 5. 60 B 尾块")
print("=" * 100)
for k in range(0, 60, 16):
    print("  +0x%02X  %-47s  |%s|" % (k, " ".join("%02x" % c for c in TAIL[k:k + 16]),
          "".join(chr(c) if 32 <= c < 127 else '.' for c in TAIL[k:k + 16])))
