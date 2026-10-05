# -*- coding: utf-8 -*-
"""R12-3 ★★ 帧假设的【分辨力检验】（先验纪律：任何"能对上"的解析都必须先证明它捞得出已知答案，
        且在对照上失败）
 假设 H_frame：cfg body 的某段是 [TAG:u8][LEN:u8][payload LEN-2] 的链
 问题：本机 cfg body 从 +0x132 起能连出 6 帧正好闭合 —— 这是【结构】还是【巧合】？
 检验：① 在整份 cfg body 上，从【每一个】起点尝试链式解析，统计最长闭环；
       ② 用【同长度随机数据】+【打乱字节】做对照，看同样长度能否达成；
       ③ 用 capA（同一格式）复现，看闭链位置是否一致。
"""
import random, os

def load(p, base):
    return open(p, 'rb').read()[base:base+1024]

N = {'本机': (load('orig_TB14P.bin', 0x4C), 0x4C),
     'capA': (load('cap22001E0D.Cap', 0xA4), 0xA4),
     'capB': (load('cap26002816.Cap', 0xA4), 0xA4)}

def chain(d, start, maxframe=64):
    """[TAG][LEN][payload LEN-2]，返回 (帧数, 结束偏移)"""
    o = start; n = 0
    while o < len(d):
        if len(d) - o < 2: break
        ln = d[o+1]
        if ln < 2 or ln > maxframe: break
        o += ln; n += 1
        if n > 40: break
    return n, o

print("=" * 100)
print("### 1 逐起点链式解析：最长闭链（本机 cfg body）")
print("=" * 100)
for nm, (d, base) in N.items():
    best = []
    for s in range(len(d) - 2):
        n, e = chain(d, s)
        if n >= 4:
            best.append((n, s, e))
    best.sort(reverse=True)
    print(f"\n--- {nm} (cfg body @{hex(base)}) ---  长度≥4 的闭链起点 {len(best)} 个")
    for n, s, e in best[:8]:
        print(f"   起点 {hex(s)}（绝对 {hex(base+s)}）帧数={n} 终点={hex(e)}  字节: " +
              ' '.join('%02x' % x for x in d[s:min(e, s+40)]))

print("\n" + "=" * 100)
print("### 2 ★ 对照：同长度【真随机】数据，看闭链能不能同样长（分辨力）")
print("=" * 100)
random.seed(7)
for trial in range(3):
    r = bytes(random.randrange(256) for _ in range(1024))
    bb = [(chain(r, s)[0], s) for s in range(1022)]
    bb.sort(reverse=True)
    print(f"  随机样本{trial}: 最长闭链 {bb[0][0]} 帧 @{hex(bb[0][1])}  "
          f"（对比：本机最长 {max(chain(N['本机'][0], s)[0] for s in range(1022))}）")

print("\n" + "=" * 100)
print("### 3 ★ 对照：把本机 cfg body 的字节【随机打乱】（保留直方图），看闭链长度")
print("=" * 100)
d0 = N['本机'][0]
hist = list(d0); random.shuffle(hist); hist = bytes(hist)
hb = [(chain(hist, s)[0], s) for s in range(1022)]; hb.sort(reverse=True)
print(f"  打乱后最长闭链 {hb[0][0]} 帧 @{hex(hb[0][1])}")

print("\n" + "=" * 100)
print("### 4 对照：只在【零段】上打乱（保留长零段）——  零字节是否就是[链能连下去]的原因")
print("=" * 100)
# 统计 LEN 值分布（链上出现的 LEN）
from collections import Counter
c = Counter()
for s in range(1022):
    o = s; n = 0
    while o < 1023:
        ln = d0[o+1]
        if ln < 2 or ln > 64: break
        c[ln] += 1; o += ln; n += 1
        if n > 40: break
print("  链上 LEN 值频次 top12:", c.most_common(12))
print("  全 body 字节频次 top12:", Counter(d0.tolist()).most_common(12))
