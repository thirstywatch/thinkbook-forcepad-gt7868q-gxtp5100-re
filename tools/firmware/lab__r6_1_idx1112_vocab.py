# -*- coding: utf-8 -*-
"""R6-1: (T2) idx11/idx12 与两个 16KB type-0x02 组；(T1) 词表跨块共享的零密度校正"""
import numpy as np, collections, math

S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0), 'capB': ('cap26002816.Cap', 0x4F0)}

def load(p, base):
    d = open(p, 'rb').read(); n = d[base+27]; q = base+32; rows = []
    for _ in range(n):
        rows.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                     ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
    tot = sum(r[1] for r in rows)
    return rows, np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)

R, RAW = {}, {}
for k, (p, b) in S.items():
    R[k], RAW[k] = load(p, b)
ROWS = R['本机']; OFF = np.cumsum([0] + [r[1] for r in ROWS])
print("idx / type / flash / size:")
for i, (t, ln, ad) in enumerate(ROWS):
    print(f"  {i:>2}  type {t:#04x}  flash {ad:#07x}-{ad+ln-1:#07x}  size {ln}")

print("\n" + "="*96)
print("### T2-a ★ 按 flash 地址排序：type 0x02 的块是否组成连续的 16 KB 组？")
print("="*96)
by_addr = sorted(range(len(ROWS)), key=lambda i: ROWS[i][2])
for i in by_addr:
    t, ln, ad = ROWS[i]
    print(f"  flash {ad:#07x}-{ad+ln-1:#07x}  idx{i:>2}  type {t:#04x}  size {ln}")
t02 = sorted([i for i in range(len(ROWS)) if ROWS[i][0] == 0x02], key=lambda i: ROWS[i][2])
print(f"\n  type 0x02 的块: {[(f'idx{i}', hex(ROWS[i][2]), ROWS[i][1]) for i in t02]}")
g1 = [i for i in t02 if ROWS[i][2] < 0x10000]
g2 = [i for i in t02 if ROWS[i][2] >= 0x10000]
def span(g):
    los = min(ROWS[i][2] for i in g); his = max(ROWS[i][2]+ROWS[i][1] for i in g)
    return f"{los:#07x}-{his-1:#07x} ({(his-los)//1024} KB)"
print(f"  ★ 组 1 = {[f'idx{i}' for i in g1]}  → flash {span(g1)}")
print(f"  ★ 组 2 = {[f'idx{i}' for i in g2]}  → flash {span(g2)}")

print("\n" + "="*96)
print("### T2-b ★ 同尺寸的 type-0x02 块两两比较（4096 对 4096；12288 对 12288）")
print("="*96)
def cmp_blocks(i, j, label):
    oi, oj = OFF[i], OFF[j]; m = min(ROWS[i][1], ROWS[j][1])
    a = RAW['本机'][oi:oi+m]; b = RAW['本机'][oj:oj+m]
    eq = (a == b)
    # 最长连续相同前缀
    k = 0
    while k < m and a[k] == b[k]: k += 1
    print(f"  {label}: idx{i}({ROWS[i][2]:#x}) vs idx{j}({ROWS[j][2]:#x})  相同率 {100*eq.mean():5.2f}%  "
          f"连续同前缀 {k} B")
    return eq
cmp_blocks(9, 12, "4096 组")
cmp_blocks(8, 11, "12288 组")
cmp_blocks(9, 8, "组1 内部")
cmp_blocks(12, 11, "组2 内部")
for x in (8, 9):
    for y in (11, 12):
        cmp_blocks(x, y, "跨组")

print("\n" + "="*96)
print("### T2-c ★★ idx11/idx12 的跨样本不变量：三份全同的字节在哪？")
print("="*96)
for i in (11, 12, 8, 9):
    o, ln = OFF[i], ROWS[i][1]
    X = np.stack([RAW[k][o:o+ln] for k in S])
    same = (X[0] == X[1]) & (X[1] == X[2])
    # 连续段
    segs, s = [], None
    for j in range(ln):
        if same[j] and s is None: s = j
        elif not same[j] and s is not None: segs.append((s, j-1)); s = None
    if s is not None: segs.append((s, ln-1))
    big = [x for x in segs if x[1]-x[0]+1 >= 8]
    print(f"\n  idx{i} flash {ROWS[i][2]:#07x} size {ln}: 三份全同 {int(same.sum())} B ({100*same.mean():.1f}%)")
    print(f"    ≥8B 的连续恒定段 {len(big)} 个（前 10）: "
          f"{[(hex(a), hex(b), b-a+1) for a, b in big[:10]]}")
    if big:
        a, b = big[0]
        print(f"    第一段内容: {" ".join(f"{c:02x}" for c in RAW['本机'][o+a:o+min(b+1,a+48)])}")
    # 起始 32 字节三份对比
    print(f"    起始 16B: 本机 {" ".join(f"{c:02x}" for c in RAW['本机'][o:o+16])}")
    print(f"               capA {" ".join(f"{c:02x}" for c in RAW['capA'][o:o+16])}")
    print(f"               capB {" ".join(f"{c:02x}" for c in RAW['capB'][o:o+16])}")
    c = collections.Counter(RAW['本机'][o:o+ln].tolist())
    H = -sum((v/ln)*math.log2(v/ln) for v in c.values())
    print(f"    零% {100*c[0]/ln:.2f}  熵 {H:.3f}  distinct 字节 {len(c)}/256  "
          f"top1 {c.most_common(1)[0][0]:#04x}×{c.most_common(1)[0][1]}")

print("\n" + "="*96)
print("### T1 ★★ 词表跨块共享 —— 零密度校正（置换零模型）")
print("="*96)
K = {}
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    w = RAW['本机'][o:o+ln - ln % 4]
    K[i] = collections.Counter(bytes(x) for x in w.reshape(-1, 4))
rng = np.random.default_rng(2026)
NNULL = 60
print(f"  零模型：把两块各自的字节【打乱】（保留各自的字节直方图 ⇒ 保留零密度），算共享词数的分布（{NNULL} 次）")
print(f"  {'对':<12} {'观测共享':>8} {'零模型均值':>10} {'零模型σ':>8} {'z':>7}  判读")
rows_out = []
for i in range(len(ROWS)):
    for j in range(i+1, len(ROWS)):
        obs = len(set(K[i]) & set(K[j]))
        bi = RAW['本机'][OFF[i]:OFF[i]+ROWS[i][1] - ROWS[i][1] % 4].tobytes()
        bj = RAW['本机'][OFF[j]:OFF[j]+ROWS[j][1] - ROWS[j][1] % 4].tobytes()
        vals = []
        for _ in range(NNULL):
            si = set(bytes(x) for x in np.frombuffer(rng.permutation(np.frombuffer(bi, np.uint8)).tobytes(), np.uint8).reshape(-1, 4))
            sj = set(bytes(x) for x in np.frombuffer(rng.permutation(np.frombuffer(bj, np.uint8)).tobytes(), np.uint8).reshape(-1, 4))
            vals.append(len(si & sj))
        mu = float(np.mean(vals)); sd = float(np.std(vals)) or 1e-9
        z = (obs - mu) / sd
        rows_out.append((z, i, j, obs, mu, sd))
rows_out.sort(reverse=True)
for z, i, j, obs, mu, sd in rows_out[:14]:
    tag = "★★强共享" if z > 20 else ("★共享" if z > 5 else ("弱/无" if z > 2 else "≈噪声"))
    print(f"  idx{i:>2}-idx{j:<2}   {obs:>8}   {mu:>10.1f}   {sd:>8.2f} {z:>7.1f}  {tag}")
print(f"\n  （共 {len(rows_out)} 对；z>20 的前 8 对："
      f"{[(f'{i}-{j}', round(z,1)) for z,i,j,_,_,_ in rows_out[:8]]}）")
