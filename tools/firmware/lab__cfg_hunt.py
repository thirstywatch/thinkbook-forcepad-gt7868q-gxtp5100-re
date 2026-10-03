# -*- coding: utf-8 -*-
"""通用 cfg 探测器：在任意文件里找"64 B 头 + [LEN][TAG] 流"的结构
   判据（自校验，极难偶然命中）：
     设 TLV 起点 S，则  u16LE@(S-5) == 文件长 - S      ← 长度闭合
                        u8@(S-3)    == TLV 实际条目数   ← 计数闭合
                        走完后 TAG 全部严格递增
"""
import os, sys, struct, glob

def walk(buf, st):
    i = st; out = []
    while i + 2 <= len(buf):
        ln = buf[i]; tag = buf[i+1]
        if ln < 2 or i + ln > len(buf):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, buf[i+2:i+ln])); i += ln
    return out

def detect(d):
    """返回所有满足自校验的 (S, 条目数) """
    res = []
    for S in range(0x20, min(len(d) - 8, 0x400)):
        L = struct.unpack_from('<H', d, S - 5)[0]
        if L != len(d) - S:
            continue
        cnt = d[S-3]
        # 只走 TLV 区（S..S+L），末尾允许 4 B 尾部（实测 sid0/sid3 都有）
        w = walk(d[:S+L], S)
        complete = [x for x in w if x[3] is not None]
        used = (complete[-1][0] + complete[-1][2]) - S if complete else 0
        if len(complete) != cnt:
            continue
        if not (L - used) in (0, 2, 4, 6):
            continue
        tags = [x[1] for x in complete]
        if not all(b > a for a, b in zip(tags, tags[1:])):
            continue
        res.append((S, cnt, len(w)))
    return res

ROOTS = [r"<WORKSPACE>",
         r"<WORKSPACE>",
         r"<LAB>\touchpad-lab"]

MIN, MAX = 200, 200000
seen = set()
for root in ROOTS:
    for dirpath, dirnames, filenames in os.walk(root):
        if '_bak' in dirpath: continue
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if not (MIN <= sz <= MAX): continue
            try:
                d = open(p, 'rb').read()
            except OSError:
                continue
            r = detect(d)
            if r:
                key = (sz, r[0][0], r[0][1])
                if key in seen: continue
                seen.add(key)
                print("★ %s  (%d B)  ->  %s" % (p, sz, r))
print("扫描完毕。")
