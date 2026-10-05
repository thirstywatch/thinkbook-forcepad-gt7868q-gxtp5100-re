# -*- coding: utf-8 -*-
"""R4-7: 三份 GT7868Q 镜像 —— 官方格式复核 + 相位自适应 + 跨样本 + 13 块结构解析"""
import collections, math, numpy as np

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)

SAMPLES = {
    'TB14P(本机)':  ('orig_TB14P.bin', 0x113C),
    'cap22001E0D':  ('cap22001E0D.Cap', 0x4F0),
    'cap26002816':  ('cap26002816.Cap', 0x4F0),
}

def parse(img):
    size = int.from_bytes(img[0:4], 'big'); chk = int.from_bytes(img[4:6], 'big')
    real = sum(img[6:size+6]) & 0xFFFF
    n = img[27]; p = 32; off = 256; subs = []
    for _ in range(n):
        t = img[p]
        ln = (img[p+1] << 24) | (img[p+2] << 16) | (img[p+3] << 8) | img[p+4]
        ad = ((img[p+5] << 8) | img[p+6]) << 8
        subs.append((t, ln, ad, off)); off += ln; p += 8
    return dict(size=size, chk=chk, real=real, ok=(chk == real), pid=img[15:23],
                cid=img[23], vid=tuple(img[24:27]), family=img[6:12],
                num=n, subs=subs,
                raw=np.frombuffer(img[256:256+sum(s[1] for s in subs)], dtype=np.uint8))

print("=" * 96)
print("### 1. 三份镜像的官方格式复核")
print("=" * 96)
P = {}
for name, (path, base) in SAMPLES.items():
    img = open(path, 'rb').read()[base:]
    r = parse(img); P[name] = r
    print(f"  {name:<14} 家族={r['family'].decode('latin-1')} PID={r['pid'][:5].decode('latin-1')} "
          f"CID={r['cid']:#04x} VID={r['vid'][0]}.{r['vid'][1]}.{r['vid'][2]} "
          f"size={r['size']} 校验和=0x{r['chk']:04x} {'✓OK' if r['ok'] else '✗'} 子固件={r['num']}")

base_name = 'TB14P(本机)'
tbl0 = [(t, ln, ad) for t, ln, ad, _ in P[base_name]['subs']]
for name in SAMPLES:
    t = [(x[0], x[1], x[2]) for x in P[name]['subs']]
    print(f"  子固件表与 {base_name} 完全一致? {name}: {t == tbl0}")
print("  表项:", [(hex(t), ln, hex(a)) for t, ln, a in tbl0])

print("\n" + "=" * 96)
print("### 2. 解扰相位（自适应搜索：最大化 0x00 数 / 最长零段）")
print("=" * 96)
def descramble(raw, phase):
    idx = (np.arange(len(raw)) + phase) % 1024
    return raw ^ K[idx]

def longest_zero(x):
    best = cur = 0
    for v in x:
        cur = cur + 1 if v == 0 else 0
        best = max(best, cur)
    return best

DEC = {}
for name, (path, base) in SAMPLES.items():
    raw = P[name]['raw']
    best = None
    for ph in range(1024):
        d = descramble(raw, ph)
        z = int((d == 0).sum()); lz = longest_zero(d)
        score = (z, lz)
        if best is None or score > best[0]:
            best = (score, ph, d)
    (z, lz), ph, d = best
    DEC[name] = d
    # 次优
    scores = []
    for p2 in range(1024):
        dd = descramble(raw, p2)
        scores.append((int((dd == 0).sum()), longest_zero(dd), p2))
    scores.sort(reverse=True)
    print(f"  {name:<14} 最优相位={ph:<5} 0x00={z:<6} 最长零段={lz:<5} | 次优 0x00={scores[1][0]} "
          f"(倍率 {z/max(1,scores[1][0]):.2f}×)  绝对偏移相位={ (base+256)%1024 }")
    print(f"                 descrambled 存储 → {name}")

print("\n" + "=" * 96)
print("### 3. 跨样本：按【子固件】比较（同表序）")
print("=" * 96)
names = list(SAMPLES)
print(f"  {'idx':>3} {'type':>5} {'flash':>9} {'size':>6} | " +
      " | ".join(f"{a[:10]:>10} vs {b[:10]:>10}" for a, b in
                 [('cap22001E0D','cap26002816'),('TB14P(本机)','cap22001E0D'),('TB14P(本机)','cap26002816')]))
for i, (t, ln, ad) in enumerate(tbl0):
    o = P[base_name]['subs'][i][3]
    def sl(nm): return DEC[nm][o:o+ln]
    row = []
    for a, b in [('cap22001E0D','cap26002816'),('TB14P(本机)','cap22001E0D'),('TB14P(本机)','cap26002816')]:
        x, y = sl(a), sl(b)
        m = min(len(x), len(y))
        row.append(f"{100*(x[:m]==y[:m]).mean():9.1f}%")
    print(f"  {i:>3} {t:#05x} {ad:#09x} {ln:>6} | " + " | ".join(row))

print("\n" + "=" * 96)
print("### 4. 复核 §八：flash 0x10000(idx7) 与 flash 0x01000(idx8) 的共享段")
print("=" * 96)
o7 = P[base_name]['subs'][7][3]; l7 = P[base_name]['subs'][7][1]
o8 = P[base_name]['subs'][8][3]; l8 = P[base_name]['subs'][8][1]
for name in names:
    b7 = DEC[name][o7:o7+l7]; b8 = DEC[name][o8:o8+l8]
    m = min(len(b7), len(b8))
    eq = (b7[:m] == b8[:m])
    j = 0
    while j < m and b7[j] == b8[j]: j += 1
    print(f"  {name:<14} 同相对偏移相同率={100*eq.mean():5.2f}%  从块首连续相同={j} B (0x{j:x})")

print("\n" + "=" * 96)
print("### 5. 13 块结构解析：记录宽度检测（列熵 vs 同长度打乱对照）")
print("=" * 96)
def colent(x, W):
    n = len(x) // W * W
    a = np.frombuffer(x[:n], dtype=np.uint8).reshape(-1, W)
    tot = 0.0
    for c in range(W):
        col = a[:, c]
        cnt = collections.Counter(col.tolist()); t = len(col)
        tot += -sum((v/t)*math.log2(v/t) for v in cnt.values())
    return tot / W
rng = np.random.default_rng(7)
print(f"  {'idx':>3} {'flash':>9} {'size':>6} | " +
      " | ".join(f"W={w:<2}" for w in (2,4,8,16,32)) + "   （真值 / 打乱对照，差越大结构越强）")
for i, (t, ln, ad) in enumerate(tbl0):
    o = P[base_name]['subs'][i][3]
    x = DEC[base_name][o:o+ln].tobytes()
    sh = bytes(rng.permutation(list(x)))
    cells = []
    for w in (2,4,8,16,32,64):
        pass
    for w in (2,4,8,16,32):
        cells.append(f"{colent(x,w):.3f}/{colent(sh,w):.3f}")
    print(f"  {i:>3} {ad:#09x} {ln:>6} | " + " | ".join(f"{c:<11}" for c in cells))

print("\n" + "=" * 96)
print("### 6. 字节级'骨架图'：三份全相同 vs 全不同 的位置分布（按块）")
print("=" * 96)
print(f"  {'idx':>3} {'flash':>9} | 三份全相同 三份全不同  其余 | 相同字节的分布（16 等分）")
for i, (t, ln, ad) in enumerate(tbl0):
    o = P[base_name]['subs'][i][3]
    A = np.stack([DEC[n][o:o+ln] for n in names])
    same = (A[0] == A[1]) & (A[1] == A[2])
    diff = (A[0] != A[1]) & (A[1] != A[2])
    other = ~(same | diff)
    prof = same.reshape(16, -1).mean(axis=1)
    print(f"  {i:>3} {ad:#09x} | {int(same.sum()):>9} {int(diff.sum()):>9} {int(other.sum()):>5} | " +
          " ".join(f"{100*v:4.0f}" for v in prof) + "%")
