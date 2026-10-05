# -*- coding: utf-8 -*-
"""R6-4: 压缩率标定 —— 用真代码/真数据校准"可压率"这把尺子；并看跨块共享词到底是什么"""
import numpy as np, collections, math, zlib, lzma

K = np.frombuffer(open('K.bin', 'rb').read(), dtype=np.uint8)
PH = 572
d = open('orig_TB14P.bin', 'rb').read()
base = 0x113C
n = d[base+27]; q = base+32; ROWS = []
for _ in range(n):
    ROWS.append((d[q], (d[q+1] << 24) | (d[q+2] << 16) | (d[q+3] << 8) | d[q+4],
                 ((d[q+5] << 8) | d[q+6]) << 8)); q += 8
tot = sum(r[1] for r in ROWS)
RAW = np.frombuffer(d[base+256:base+256+tot], dtype=np.uint8)
OFF = np.cumsum([0] + [r[1] for r in ROWS])
PLAIN = RAW ^ K[(np.arange(len(RAW)) + PH) % 1024]
TF = np.frombuffer(d[0x19ABC:0x2775C], dtype=np.uint8)            # 真 Cortex-M 代码
TFCODE = np.frombuffer(d[0x19ABC:0x19ABC+0x4000], dtype=np.uint8)  # 取前 16KB 代码

def zr(x):
    b = x.tobytes()
    return len(zlib.compress(b, 9))/len(b), len(lzma.compress(b))/len(b)

print("=" * 104)
print("### ★★★ 压缩率标定表：真代码 / 真数据 / 随机 / 载荷A 各块")
print("=" * 104)
rng = np.random.default_rng(9)
cal = [
    ("TF100A 真 ARM 代码(前16KB)", TFCODE),
    ("TF100A 全量 56.6KB", TF),
    ("TF100A 其中 AT文本区(含版本串)", TF[0x3E00:0x4A00]),
    ("纯随机 12KB", rng.integers(0, 256, 12288).astype(np.uint8)),
    ("全零 12KB", np.zeros(12288, dtype=np.uint8)),
]
print(f"  {'样本':<34} {'长度':>6} {'zlib率':>8} {'lzma率':>8}  判读")
for nm, x in cal:
    z, l = zr(x)
    print(f"  {nm:<34} {len(x):>6} {z:>8.4f} {l:>8.4f}")
print()
print(f"  {'idx':>3} {'type':>5} {'flash':>9} {'size':>6} | {'PLAIN zlib':>10} {'PLAIN lzma':>10} | "
      f"{'RAW zlib':>9} | 判读")
for i, (t, ln, ad) in enumerate(ROWS):
    o = OFF[i]
    pz, pl = zr(PLAIN[o:o+ln]); rz, _ = zr(RAW[o:o+ln])
    judge = ("像代码/结构化" if pl < 0.88 else ("弱结构" if pl < 0.97 else "≈不可压"))
    print(f"  {i:>3} {t:#05x} {ad:#09x} {ln:>6} | {pz:>10.4f} {pl:>10.4f} | {rz:>9.4f} | {judge}")

print("\n" + "=" * 104)
print("### ★ 跨块共享词到底是什么？（idx5-idx10 = 156 个；idx5-idx8 = 154 个）")
print("=" * 104)
def wset(i):
    o, ln = OFF[i], ROWS[i][1]
    return set(bytes(x) for x in PLAIN[o:o+ln-ln % 4].reshape(-1, 4))
for a, b in ((5, 10), (5, 8), (7, 8), (8, 11), (3, 12)):
    sh = wset(a) & wset(b)
    zc = collections.Counter(sum(1 for c in w if c == 0) for w in sh)
    print(f"\n  idx{a}-idx{b}: 共享 {len(sh)} 个词；按「词内零字节个数」分布 = {dict(sorted(zc.items()))}")
    ex = sorted(sh)[:10]
    print(f"    示例: {[w.hex(' ') for w in ex]}")
    ex2 = sorted(sh)[len(sh)//2:len(sh)//2+6]
    print(f"    中段: {[w.hex(' ') for w in ex2]}")
