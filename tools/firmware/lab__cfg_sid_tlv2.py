# -*- coding: utf-8 -*-
"""tpcfgsid*.cfg：TLV 结构判定（含"TAG 是否唯一/递增"这一强判据）+ 反例标定"""
import os, collections, random

BASE = r"<WORKSPACE>"
FILES = [("sid0", "sid0.bin"), ("sid2", "sid2.bin"), ("sid3", "sid3.bin")]

def walk_u8(d, st, end=None):
    """TAG(u8) LEN(u8) payload(LEN)"""
    end = len(d) if end is None else end
    i = st; out = []
    while i + 1 < end:
        tag = d[i]; ln = d[i+1]
        if i + 2 + ln > end:
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, d[i+2:i+2+ln])); i += 2 + ln
    return out

def walk_u16le(d, st, end=None):
    end = len(d) if end is None else end
    i = st; out = []
    while i + 2 < end:
        tag = d[i]; ln = int.from_bytes(d[i+1:i+3], 'little')
        if i + 3 + ln > end or ln == 0:
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, d[i+3:i+3+ln])); i += 3 + ln
    return out

def walk_u16be(d, st, end=None):
    end = len(d) if end is None else end
    i = st; out = []
    while i + 2 < end:
        tag = d[i]; ln = int.from_bytes(d[i+1:i+3], 'big')
        if i + 3 + ln > end or ln == 0:
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, d[i+3:i+3+ln])); i += 3 + ln
    return out

WALKS = {"u8": walk_u8, "u16le": walk_u16le, "u16be": walk_u16be}

def score(d, st, fn):
    w = fn(d, st)
    used = sum(2 + (0 if x[3] is None else x[2]) if fn is walk_u8
               else 3 + (0 if x[3] is None else x[2]) for x in w)
    tags = [x[1] for x in w if x[3] is not None]
    trunc = any(x[3] is None for x in w)
    return used, w, tags, trunc

def shuffle_null(d, fn, n=40):
    got = []
    for _ in range(n):
        y = bytearray(d); random.shuffle(y)
        best = max(score(bytes(y), st, fn)[0] for st in range(0x2b, 0x60))
        got.append(best / len(d))
    return sum(got) / len(got)

for name, fn in FILES:
    p = os.path.join(BASE, fn)
    d = open(p, 'rb').read()
    print("=" * 78)
    print("### %s  %d B" % (name, len(d)))
    for wname, wfn in WALKS.items():
        best = None
        for st in range(0x2b, 0x60):
            used, w, tags, trunc = score(d, st, wfn)
            if best is None or used > best[0]:
                best = (used, st, w, tags, trunc)
        used, st, w, tags, trunc = best
        r = used / len(d)
        nullm = shuffle_null(d, wfn)
        cnt = collections.Counter(tags)
        dup = sum(1 for k, v in cnt.items() if v > 1)
        asc = sum(1 for a, b in zip(tags, tags[1:]) if b >= a) / max(1, len(tags)-1)
        print("  格式 %-6s 最优起点 0x%02X  覆盖 %.1f%%  打乱对照 %.1f%%  Δ=%+.1f pt  块数 %d  截断 %s  TAG重复种数 %d  非降序比 %.2f"
              % (wname, st, r*100, nullm*100, (r-nullm)*100, len(w), trunc, dup, asc))
