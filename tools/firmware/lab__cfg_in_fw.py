# -*- coding: utf-8 -*-
"""tpcfgsid0 的 TLV 条目是否逐字节出现在本机固件里？（决定性交叉验证）"""
import os, collections

LAB = r"<LAB>\touchpad-lab"
CFG = r"<WORKSPACE>"
FW = open(os.path.join(LAB, "bios-re", "GT7868Q_native_fw.bin"), 'rb').read()
PLAIN = open(os.path.join(LAB, "poc", "decrypt-v2", "GT7868Q_2024_本机_plain_data.bin"), 'rb').read()

def find(hay, needle, limit=20):
    out = []; i = 0
    while True:
        j = hay.find(needle, i)
        if j < 0: break
        out.append(j)
        if len(out) >= limit: break
        i = j + 1
    return out

def lcs_pairs(a, b, minlen=8, limit=40):
    """a 的每个位置在 b 中的最长匹配（≥minlen），去重后返回 (a_off, b_off, len)"""
    idx = collections.defaultdict(list)
    for i in range(0, len(b) - minlen + 1):
        idx[b[i:i+minlen]].append(i)
    res = []; i = 0
    while i <= len(a) - minlen:
        best = 0; bo = -1
        for j in idx.get(a[i:i+minlen], []):
            L = minlen
            while i + L < len(a) and j + L < len(b) and a[i+L] == b[j+L]:
                L += 1
            if L > best: best = L; bo = j
        if best >= minlen:
            res.append((i, bo, best)); i += best
        else:
            i += 1
    res.sort(key=lambda x: -x[2])
    return res[:limit]

print("=" * 78)
print("### 1. sid0 的每条 TLV 条目，在固件里逐字节搜（含头）")
s0 = open(os.path.join(CFG, "sid0.bin"), 'rb').read()

def walk(d, st):
    i = st; out = []
    while i + 2 <= len(d):
        ln = d[i]; tag = d[i+1]
        if ln < 2 or i + ln > len(d):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, d[i+2:i+ln])); i += ln
    return out

w = [x for x in walk(s0, 0x40) if x[3] is not None]
print("  共 %d 条完整条目" % len(w))
hits = 0
for off, tag, ln, pl in w:
    ent = s0[off:off+ln]                      # 含 LEN/TAG 头
    pl_only = pl
    h1 = find(FW, ent)
    h2 = find(PLAIN, ent)
    h3 = find(FW, pl_only) if len(pl_only) >= 6 else []
    mark = ""
    if h1 or h2: mark += " FW-ENT" if h1 else ""; mark += " PLAIN-ENT" if h2 else ""
    if h3: mark += " FW-PAYLOAD"
    if mark:
        hits += 1
        print("  TAG 0x%02X LEN %-3d 头偏移 0x%03X | FW@%s PLAIN@%s FW(payload)@%s |%s"
              % (tag, ln, off,
                 [hex(x) for x in h1[:3]], [hex(x) for x in h2[:3]],
                 [hex(x) for x in h3[:3]], mark))
print("  ⇒ 有命中条目 %d / %d" % (hits, len(w)))

print()
print("=" * 78)
print("### 2. sid0 整个 TLV 区（0x40..0x515）与固件的最长公共子串（≥10 B）")
TLV = s0[0x40:0x40+1238]
for tag, hay, hn in (("FW", FW, "固件原图"), ("PLAIN", PLAIN, "解密后载荷A")):
    r = lcs_pairs(TLV, hay, minlen=10, limit=12)
    print("  vs %s (%d B)：最长 %s" % (hn, len(hay), r[:6] if r else "无 ≥10 B 匹配"))

print()
print("=" * 78)
print("### 3. 反向：固件外层 4412 B 里那条 `0e 02 09 a0` 是什么")
needle = bytes.fromhex("0e0209a000658000")
print("  固件中:", [hex(x) for x in find(FW, needle)[:10]])
print("  解密载荷A 中:", [hex(x) for x in find(PLAIN, needle)[:10]])
print("  sid0 里的 TAG 0x02 条目:", s0[0x7c:0x7c+14].hex(' '))
print()
print("  截断到 `0e 02` 在固件中的位置:", [hex(x) for x in find(FW, bytes.fromhex("0e02"))[:20]])

print()
print("=" * 78)
print("### 4. 固件外层 4412 B vs sid0 TLV —— 最长公共子串（≥8 B）")
OUTER = FW[0:0x113C]
r = lcs_pairs(OUTER, TLV, minlen=8, limit=12)
print("  外层(4412) 里与 sid0 TLV 匹配:", r if r else "无 ≥8 B")
r2 = lcs_pairs(OUTER, TLV, minlen=6, limit=15)
print("  放宽到 ≥6 B:", r2 if r2 else "无")
