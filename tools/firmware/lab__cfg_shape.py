# -*- coding: utf-8 -*-
"""cfg 语义路线 step1：每个 ID 的 payload "形状报告"
   —— 元素宽度判定、常量/阶梯/128 中心/索引序列的自动识别"""
import os, collections

CFG = r"<WORKSPACE>"
FILES = [("sid0", "sid0.bin", "Xiaomi 7867"), ("sid3", "sid3.bin", "LaiBao 7986P")]

def walk(buf, st=0x40):
    i = st; out = []
    while i + 2 <= len(buf):
        ln = buf[i]; tag = buf[i+1]
        if ln < 2 or i + ln > len(buf):
            out.append((i, tag, ln, None)); break
        out.append((i, tag, ln, buf[i+2:i+ln])); i += ln
    return out

# AW86927 / 常见触觉常量（ms）候选
DUR = {10, 20, 30, 40, 45, 50, 60, 80, 100, 150, 200, 300, 400, 500, 600, 800,
       1000, 1500, 2000, 3000, 4000, 5000, 8000, 10000}

def shape(pl):
    n = len(pl)
    info = []
    if n == 0: return "空"
    u8 = list(pl)
    if len(set(u8)) == 1: info.append("全常量0x%02X" % u8[0])
    # 索引序列：严格/近似递增的小值
    if n >= 4 and all(u8[i] < u8[i+1] for i in range(n-1)) and u8[-1] <= 0x80:
        info.append("严格递增索引 %d→%d" % (u8[0], u8[-1]))
    elif n >= 4 and sum(1 for i in range(n-1) if u8[i+1] == u8[i]+1) / (n-1) > 0.7:
        info.append("近递增序列")
    # u16
    if n % 2 == 0:
        for e, nm in (('little', 'LE16'), ('big', 'BE16')):
            v = [int.from_bytes(pl[i:i+2], e) for i in range(0, n, 2)]
            if len(v) < 2: continue
            rng = max(v) - min(v)
            near128 = sum(1 for x in v if 120 <= x <= 136) / len(v)
            dur = sum(1 for x in v if x in DUR) / len(v)
            tags = []
            if near128 > 0.7: tags.append("%d%%∈[120,136]" % (near128*100))
            if dur > 0.5: tags.append("时长集命中%d%%" % (dur*100))
            if all(v[i] <= v[i+1] for i in range(len(v)-1)) and len(v) >= 3 and rng > 0:
                tags.append("单调↑")
            if rng > 0: tags.append("max=%d min=%d %d项" % (max(v), min(v), len(v)))
            if tags: info.append(nm+": "+" ".join(tags))
    # 128 中心（字节）
    c = collections.Counter(u8)
    if len(u8) >= 8:
        near = sum(1 for x in u8 if 0x78 <= x <= 0x88) / len(u8)
        if near > 0.6: info.append("字节%d%%∈[0x78,0x88]" % (near*100))
    return " | ".join(info) or "-"

for nm, fn, desc in FILES:
    d = open(os.path.join(CFG, fn), 'rb').read()
    w = [x for x in walk(d) if x[3] is not None]
    print("=" * 108)
    print("### %s (%s)  %d 条" % (nm, desc, len(w)))
    print("%-5s %-4s %-4s %s" % ("ID", "LEN", "pay", "形状"))
    for off, tag, ln, pl in w:
        print("0x%02X  %-4d %-4d %s" % (tag, ln, len(pl), shape(pl)))
