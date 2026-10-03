# -*- coding: utf-8 -*-
"""[LEN][TAG] vs [TAG][LEN] 头对头（同一起点 0x40），含打乱对照与 TAG 递增性"""
import os, random

CFG = r"<WORKSPACE>"

def walk(d, st, order):
    i = st; out = []
    while i + 2 <= len(d):
        if order == 'LT':
            ln, tag = d[i], d[i+1]
        else:
            tag, ln = d[i], d[i+1]
        if ln < 2 or i + ln > len(d):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, d[i+2:i+ln])); i += ln
    return out

def metrics(d, st, order):
    w = walk(d, st, order)
    used = sum(x[2] if x[3] is not None else 0 for x in w)
    tags = [x[1] for x in w if x[3] is not None]
    trunc = any(x[3] is None for x in w)
    asc = sum(1 for a, b in zip(tags, tags[1:]) if b > a) / max(1, len(tags)-1)
    return used/len(d), len(w), asc, trunc

for nm in ("sid0", "sid3"):
    d = open(os.path.join(CFG, nm + ".bin"), 'rb').read()
    print("=" * 78)
    print("### %s (%d B)" % (nm, len(d)))
    for order in ("LT", "TL"):
        cov, n, asc, trunc = metrics(d, 0x40, order)
        nulls = []
        for _ in range(40):
            y = bytearray(d); random.shuffle(y)
            c, nn, a, t = metrics(bytes(y), 0x40, order)
            nulls.append((c, a))
        mc = sum(x[0] for x in nulls)/len(nulls)
        ma = sum(x[1] for x in nulls)/len(nulls)
        print("  %s: 起点 0x40 | 覆盖 %5.1f%% (打乱 %5.1f%%, Δ%+5.1f pt) | 块数 %-3d 截断 %-5s | "
              "TAG 严格递增 %.2f (打乱 %.2f)"
              % ("[LEN][TAG]" if order == "LT" else "[TAG][LEN]",
                 cov*100, mc*100, (cov-mc)*100, n, trunc, asc, ma))
