# -*- coding: utf-8 -*-
"""★★★ 三方对齐收尾：文件配置体(1024 B) 与 tpcfgsid0/sid3 的公共片段，各自落在哪个 TAG 内"""
import os, collections

LAB = r"<LAB>\touchpad-lab"
CFG = r"<WORKSPACE>"
d = open(os.path.join(LAB, "bios-re", "GT7868Q_native_fw.bin"), 'rb').read()
BODY = d[0x4C:0x4C+1024]

def walk(buf, st=0x40):
    i = st; out = []
    while i + 2 <= len(buf):
        ln = buf[i]; tag = buf[i+1]
        if ln < 2 or i + ln > len(buf):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, buf[i+2:i+ln])); i += ln
    return out

def lcs(a, b, minlen, limit=60):
    idx = collections.defaultdict(list)
    for i in range(0, len(b)-minlen+1):
        idx[b[i:i+minlen]].append(i)
    res = []; i = 0
    while i <= len(a)-minlen:
        best = 0; bo = -1
        for j in idx.get(a[i:i+minlen], []):
            L = minlen
            while i+L < len(a) and j+L < len(b) and a[i+L] == b[j+L]:
                L += 1
            if L > best: best, bo = L, j
        if best >= minlen:
            res.append((i, bo, best)); i += best
        else:
            i += 1
    res.sort(key=lambda x: -x[2])
    return res[:limit]

for nm in ("sid0", "sid3"):
    cfg = open(os.path.join(CFG, nm + ".bin"), 'rb').read()
    w = [(o, t, l) for o, t, l, p in walk(cfg) if p is not None]
    print("=" * 96)
    print("### 配置体(1024 B) ↔ %s（TAG 区间对照，≥8 B 公共片段）" % nm)
    r = lcs(BODY, cfg, 8, 40)
    nontrivial = []
    for boff, coff, L in r:
        frag = BODY[boff:boff+L]
        if len(set(frag)) <= 1:      # 全零/全 FF 不算
            continue
        # 该片段落在哪个 TAG 内
        tg = None
        for o, t, l in w:
            if o <= coff < o + l:
                tg = (t, o, l, coff - o); break
        nontrivial.append((boff, coff, L, tg, frag))
    print("%-9s %-9s %-4s %-22s %s" % ("体偏移", "cfg偏移", "长", "落在 TAG(LEN@偏移,条目内偏移)", "片段"))
    for boff, coff, L, tg, frag in nontrivial[:26]:
        tgs = "无(在头/TLV外)" if tg is None else "TAG 0x%02X (LEN 0x%02X @0x%04X, in+0x%X)" % tg
        print("+0x%04X  0x%04X    %-4d %-40s %s" % (boff, coff, L, tgs, frag[:24].hex(' ')))
    print("  ⇒ 非平凡公共片段 %d 段；全部落在 TAG 0x01 内 = %s"
          % (len(nontrivial), all(t and t[0] == 0x01 for _, _, _, t, _ in nontrivial) if nontrivial else "n/a"))
    print()

print("=" * 96)
print("### 对照：配置体自身有没有 [LEN][TAG] 字符（0x01..0x7A 递增对）")
pairs = [(BODY[i], BODY[i+1]) for i in range(len(BODY)-1)]
asc = [(i, a, b) for i, (a, b) in enumerate(pairs) if 2 <= a <= 0xC8 and 0x10 <= b <= 0x7F and (i == 0 or b > pairs[i-1][1] or True)]
print("  (仅作展示：配置体前 8 个 [b,b+1] 对 =", [("%02x %02x" % p) for p in pairs[:8]], ")")
