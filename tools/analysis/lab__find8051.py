# -*- coding: utf-8 -*-
"""8051 (Turbo51) 判据：中断向量表检测器
  架构必需：真 8051 程序在 0x00/0x03/0x0B/0x13/0x1B/0x23 处必然是 LJMP(02)/LCALL(12)
  专一性（随机基线）：p(byte in {02,12}) = 2/256
      P(score>=5) = C(6,5)*p^5 ~ 1.7e-10   -> 30 MB 期望假阳性 0.005
      P(score>=4) ~ 5.5e-8                 -> 30 MB 期望假阳性 1.7
  因此 score>=5 = 几乎无假阳性；score==4 = 需人工复核
"""
import os, struct, glob, collections

DET = (0x00, 0x03, 0x0B, 0x13, 0x1B, 0x23)

def scan(path, min_score=4, max_hits=40):
    try:
        b = open(path, 'rb').read()
    except Exception as e:
        return None, 0
    hits = []
    n = len(b) - 0x30
    # 快速预筛：只看这 6 个位置的字节
    for o in range(0, n):
        s = 0
        for d in DET:
            if b[o + d] in (0x02, 0x12):
                s += 1
        if s >= min_score:
            hits.append((o, s))
            if len(hits) > 4000:
                break
    # 通过 score 分布统计
    cnt = collections.Counter(s for _, s in hits)
    return (hits, cnt, len(b))

TARGETS = []
roots = [
    r"<LAB>\touchpad-lab",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
]
for r in roots:
    if os.path.isfile(r):
        TARGETS.append(r)
    else:
        for dp, dn, fn in os.walk(r):
            if any(s in dp for s in ('_bak', '_dup-archive', '__pycache__', 'node_modules')):
                continue
            for f in fn:
                if f.lower().endswith(('.bin', '.fw')) or f.lower().endswith('.bin'):
                    TARGETS.append(os.path.join(dp, f))
TARGETS = sorted(set(TARGETS), key=lambda p: -os.path.getsize(p) if os.path.exists(p) else 0)

print("== 8051 向量表检测器（专一性极高：score>=5 随机基线 ~1.7e-10） ==")
print("%-58s %-10s %-9s %-9s %s" % ("文件", "大小", ">=5", ">=4", "最佳命中(offset,score)"))
print("-" * 120)
summary = []
for p in TARGETS:
    if not os.path.exists(p): continue
    sz = os.path.getsize(p)
    if sz < 4096 or sz > 200_000_000: continue
    res = scan(p)
    if res is None: continue
    hits, cnt, n = res
    h5 = [h for h in hits if h[1] >= 5]
    h4 = [h for h in hits if h[1] == 4]
    best = max(hits, key=lambda z: z[1]) if hits else None
    tag = ""
    if h5: tag = "  <== *** STRONG ***"
    elif len(h4) > 0: tag = "  <== weak"
    if hits or sz > 1_000_000:
        print("%-58s %-10d %-9d %-9d %s%s" % (
            os.path.basename(p), sz, len(h5), len(h4),
            ("0x%X, %d" % best) if best else "-", tag))
    if h5:
        for o, s in h5[:5]:
            print("        STRONG @0x%X score=%d :: %s" % (o, s, hits and "" or ""))
            print("           bytes: " + b" ".join([]).hex() if False else "")
        summary.append((p, [o for o, _ in h5[:8]]))
print("-" * 120)
print()
if summary:
    print("== STRONG 命中的文件与偏移 ==")
    for p, offs in summary:
        b = open(p, 'rb').read()
        print("  %s" % p)
        for o in offs:
            seg = b[o:o + 0x30]
            print("     @0x%X  %s" % (o, " ".join("%02x" % c for c in seg)))
else:
    print("== 在所有被扫描文件中：score>=5 的 8051 向量表命中数 = 0 ==")
