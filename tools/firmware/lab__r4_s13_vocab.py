# -*- coding: utf-8 -*-
"""R4-13: 载荷 A 内容的"词汇表"分析 —— 4 字节词组是否小词表（opcode/tag）？"""
import numpy as np, collections, math

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
PH = 572
S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0), 'capB': ('cap26002816.Cap', 0x4F0)}

def load(p, base):
    d = open(p, 'rb').read(); n = d[base+27]; q = base+32; rows = []
    for _ in range(n):
        rows.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                     ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
    tot = sum(r[1] for r in rows)
    raw = np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)
    return rows, raw ^ K[(np.arange(len(raw)) + PH) % 1024]

rows_, P = load(*S['本机'])
ROWS = rows_; OFF = np.cumsum([0] + [r[1] for r in ROWS])

print("=" * 96)
print("### 1 ★ 4 字节词汇表：每个块的 distinct 4B 词数 与 词表熵")
print("=" * 96)
print(f"  {'idx':>3} {'flash':>9} {'size':>6} {'n/4':>6} {'distinct':>9} {'top1占比':>9} "
      f"{'词表熵':>8} {'打乱后distinct':>14}")
rng = np.random.default_rng(11)
ALLV = {}
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    w = P[o:o+ln-ln % 4]
    u32 = w.view(np.uint32)
    cnt = collections.Counter(u32.tolist())
    n = len(u32)
    H = -sum((v/n)*math.log2(v/n) for v in cnt.values())
    sh = np.frombuffer(rng.permutation(w).tobytes(), dtype=np.uint32)
    ALLV[i] = set(cnt)
    print(f"  {i:>3} {ad:#09x} {ln:>6} {n:>6} {len(cnt):>9} "
          f"{100*cnt.most_common(1)[0][1]/n:>8.2f}% {H:>8.2f} {len(set(sh.tolist())):>14}")

print("\n" + "=" * 96)
print("### 2 ★ 词表共享：块与块之间的共同 4 字节词数（若同一套指令/标签，应大量共享）")
print("=" * 96)
print("      " + "".join(f"{i:>7}" for i in range(13)))
for i in range(13):
    row = f"  {i:>3} "
    for j in range(13):
        inter = len(ALLV[i] & ALLV[j])
        row += f"{inter:>7}"
    print(row)
print("  （* 注意：小词表块的 top 词可能是'低位字节多零'造成的平凡重合）")

print("\n" + "=" * 96)
print("### 3 ★ idx4 / idx6 的 top-15 高频 4 字节词")
print("=" * 96)
for i in (4, 6, 2, 9):
    o = OFF[i]; ln = ROWS[i][1]
    u32 = P[o:o+ln-ln % 4].view(np.uint32)
    c = collections.Counter(u32.tolist())
    print(f"\n  idx{i} flash {ROWS[i][2]:#07x}  (共 {len(u32)} 词, distinct {len(c)})")
    for v, k in c.most_common(15):
        print(f"    {v:#010x}  ×{k:<5} LE字节 {' '.join(f'{b:02x}' for b in v.to_bytes(4,'little'))}"
              f"  BE字节 {' '.join(f'{b:02x}' for b in v.to_bytes(4,'big'))}")

print("\n" + "=" * 96)
print("### 4 ★ 16 字节记录：是否存在完整重复记录（模板库？）")
print("=" * 96)
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    recs = P[o:o+ln//16*16].reshape(-1, 16)
    c = collections.Counter(bytes(r) for r in recs)
    dup = sum(v-1 for v in c.values() if v > 1)
    top = c.most_common(3)
    print(f"  idx{i:>2} {ad:#07x} 记录数 {len(recs):>4} distinct {len(c):>4} 重复记录 {dup:>4}  "
          f"最高频×{top[0][1] if top else 0}  {top[0][0].hex(' ') if top else ''}")

print("\n" + "=" * 96)
print("### 5 ★ 128 字节超记录：64 个 128B 记录两两相同率（模板库/AB 副本？）")
print("=" * 96)
for i in (4, 6, 2, 9, 7):
    o = OFF[i]; ln = ROWS[i][1]; n = ln // 128
    if n < 4: continue
    recs = P[o:o+n*128].reshape(n, 128)
    # 用 16B 子块指纹法：统计每个 128B 记录中 16B 子块与其他记录共享的个数
    subs = [set(bytes(recs[r][k*16:k*16+16]) for k in range(8)) for r in range(n)]
    best = []
    for a in range(n):
        for b in range(a+1, n):
            best.append(len(subs[a] & subs[b]))
    if best:
        best = np.array(best)
        print(f"  idx{i:>2} {ad:#07x} 128B记录 {n} 条, 两两共享 16B 子块数: 均值 {best.mean():.2f} "
              f"最大 {best.max()}（理论上限 8）")
