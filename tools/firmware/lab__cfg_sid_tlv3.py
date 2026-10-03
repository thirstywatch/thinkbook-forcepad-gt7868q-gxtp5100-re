# -*- coding: utf-8 -*-
"""tpcfgsid*.cfg 的真实帧格式判定：[LEN u8][TAG u8][payload LEN-2]"""
import os, collections, random

BASE = r"<WORKSPACE>"
FILES = [("sid0", "sid0.bin"), ("sid2", "sid2.bin"), ("sid3", "sid3.bin")]

def walk(d, st):
    """[LEN u8][TAG u8][payload LEN-2]；LEN 含 2 字节头"""
    i = st; out = []
    while i + 2 <= len(d):
        ln = d[i]; tag = d[i+1]
        if ln < 2 or i + ln > len(d):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, d[i+2:i+ln])); i += ln
    return out

def stat(d, st):
    w = walk(d, st)
    used = sum(x[2] if x[3] is not None else 0 for x in w)
    tags = [x[1] for x in w if x[3] is not None]
    trunc = any(x[3] is None for x in w)
    asc = sum(1 for a, b in zip(tags, tags[1:]) if b > a) / max(1, len(tags)-1)
    return used, w, tags, trunc, asc

for name, fn in FILES:
    d = open(os.path.join(BASE, fn), 'rb').read()
    print("=" * 78)
    print("### %s  %d B" % (name, len(d)))
    best = None
    for st in range(0x2b, 0x80):
        used, w, tags, trunc, asc = stat(d, st)
        if best is None or used > best[0]:
            best = (used, st, w, tags, trunc, asc)
    used, st, w, tags, trunc, asc = best
    print("  最优起点 0x%02X  覆盖 %.1f%% (%d/%d)  块数 %d  截断 %s  TAG严格递增比 %.2f  末块收尾@0x%X"
          % (st, used/len(d)*100, used, len(d), len(w), trunc, asc, w[-1][0] + (w[-1][2] if w[-1][3] is not None else 0)))
    # 打乱对照
    nulls = []
    for _ in range(30):
        y = bytearray(d); random.shuffle(y)
        b = max(stat(bytes(y), s)[0] for s in range(0x2b, 0x80))
        nulls.append(b/len(d))
    print("  打乱对照最优覆盖均值 %.1f%%" % (sum(nulls)/len(nulls)*100))
    # 对照：真正随机流
    rr = []
    for _ in range(30):
        y = bytes(random.randrange(256) for _ in range(len(d)))
        rr.append(max(stat(y, 0)[0]/len(d) for _ in range(1)))
        # 用固定起点 0
    print()
    print("  %-7s %-5s %-5s %-9s %s" % ("偏移", "TAG", "LEN", "payload", "内容摘要"))
    for off, tag, ln, pl in w:
        if pl is None:
            print("  %-7s 0x%02X  %-5d %-9s <TRUNC>" % (hex(off), tag, ln, "")); continue
        s = pl[:26].hex(' ')
        if len(pl) > 26: s += " …"
        print("  %-7s 0x%02X  %-5d %-9d %s" % (hex(off), tag, ln, len(pl), s))
