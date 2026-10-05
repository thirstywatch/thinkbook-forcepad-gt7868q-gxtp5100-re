# -*- coding: utf-8 -*-
"""R6-3: 魔数扫描 + 压缩复查 + (T1修正) 词表共享的【逐列置换】零模型"""
import numpy as np, collections, math, zlib, bz2, lzma

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
PH = 572
S = {'本机': ('orig_TB14P.bin', 0x113C), 'capA': ('cap22001E0D.Cap', 0x4F0), 'capB': ('cap26002816.Cap', 0x4F0)}

def load(p, base):
    d = open(p, 'rb').read(); n = d[base+27]; q = base+32; rows = []
    for _ in range(n):
        rows.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                     ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
    tot = sum(r[1] for r in rows)
    return rows, np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)

ROWS, RAW = load(*S['本机'])
OFF = np.cumsum([0] + [r[1] for r in ROWS])
PLAIN = RAW ^ K[(np.arange(len(RAW)) + PH) % 1024]

print("=" * 100)
print("### 1 ★ 魔数扫描：两个 4096 块的头 `60 a0 88 8b` 与 idx8 的头 `c3 00 00 20` 还出现在哪？")
print("=" * 100)
for magic in (bytes.fromhex('60a0888b'), bytes.fromhex('c3000020'), bytes.fromhex('89899af7')):
    for nm, buf in (("RAW", RAW), ("PLAIN", PLAIN)):
        hits = [i for i in range(len(buf)-len(magic)) if bytes(buf[i:i+len(magic)]) == magic]
        blocks = sorted({int(np.searchsorted(OFF, h, 'right'))-1 for h in hits})
        print(f"  {magic.hex(' ')}  {nm:<5}: {len(hits)} 次  落在块 {['idx%d'%b for b in blocks][:10]}")
        if hits:
            print(f"      首 8 个偏移: {[hex(h) for h in hits[:8]]}  "
                  f"（块内: {[hex(h-OFF[int(np.searchsorted(OFF,h,'right'))-1]) for h in hits[:8]]}）")

print("\n" + "=" * 100)
print("### 2 ★ 压缩复查（zlib/bz2/lzma）：对 RAW 与 PLAIN 的 type-0x02 块都试")
print("=" * 100)
for i in (11, 12, 8, 9):
    o, ln = OFF[i], ROWS[i][1]
    for nm, x in (("RAW", RAW[o:o+ln]), ("PLAIN", PLAIN[o:o+ln])):
        raw = x.tobytes()
        z = len(zlib.compress(raw, 9)) / ln
        b = len(bz2.compress(raw, 9)) / ln
        l = len(lzma.compress(raw)) / ln
        print(f"  idx{i:>2} {nm:<5} 长度 {ln:>5}  压缩率 zlib {z:.4f}  bz2 {b:.4f}  lzma {l:.4f}  "
              f"{'★疑似压缩' if min(z,b,l) < 0.95 else '否（不可压⇒非压缩流）'}")

print("\n" + "=" * 100)
print("### 3 ★★ (T1 修正) 词表共享 —— 【逐列置换】零模型：保留每一列的字节直方图（=保留零密度）")
print("=" * 100)
def words(buf4):
    return set(bytes(x) for x in np.frombuffer(buf4, np.uint8).reshape(-1, 4))
rng = np.random.default_rng(7)
W = {}
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    blob = RAW[o:o+ln - ln % 4].tobytes()
    a = np.frombuffer(blob, np.uint8).reshape(-1, 4)
    W[i] = a
NNULL = 80
print(f"  {'对':<12} {'观测共享':>8} {'零模型μ':>9} {'σ':>7} {'z':>8}  判读")
out = []
for i in range(13):
    for j in range(i+1, 13):
        A, B = W[i], W[j]
        obs = len(words(A.tobytes()) & words(B.tobytes()))
        v = []
        for _ in range(NNULL):
            a2 = np.empty_like(A); b2 = np.empty_like(B)
            for c in range(4):
                a2[:, c] = rng.permutation(A[:, c])
                b2[:, c] = rng.permutation(B[:, c])
            v.append(len(words(a2.tobytes()) & words(b2.tobytes())))
        mu = float(np.mean(v)); sd = float(np.std(v)) or 0.5
        out.append(((obs-mu)/sd, i, j, obs, mu, sd))
out.sort(reverse=True)
for z, i, j, obs, mu, sd in out[:16]:
    tag = "★★强" if z > 30 else ("★真" if z > 8 else ("弱" if z > 3 else "≈噪声"))
    print(f"  idx{i:>2}-idx{j:<2}  {obs:>8} {mu:>9.1f} {sd:>7.2f} {z:>8.1f}  {tag}")
print(f"\n  z>3 的对数 {sum(1 for r in out if r[0]>3)}/{len(out)};  z>8 的对数 {sum(1 for r in out if r[0]>8)}")
print("  (说明) 逐列置换保留了每一列的字节直方图(零密度的来源)，因此能通过该零模型的共享必须来自列间相关性/词结构，而非零多造成的平凡重合")
