# -*- coding: utf-8 -*-
"""R4-1: 基础体检 —— 载荷A 里到底有没有"可读内容"？K 是什么形状？"""
import re, sys, collections

def rd(p):
    with open(p, 'rb') as f:
        return f.read()

A = rd('A_2024.bin')
K = rd('K.bin')
O = rd('orig_TB14P.bin')

print("=" * 78)
print("A_2024 len =", len(A), " K len =", len(K), " orig =", len(O))
print("=" * 78)

# ---------- 1. K 的形状 ----------
print("\n### 1. K (1024B) 前 128 字节")
for i in range(0, 128, 16):
    print(f"  {i:04x}  " + " ".join(f"{b:02x}" for b in K[i:i+16]))
cnt = collections.Counter(K)
print("  取值数 =", len(cnt), " 每值出现次数集合 =", sorted(set(cnt.values())))
print("  前 256 字节是否恰为 0..255 的排列 =", sorted(K[:256]) == list(range(256)))
print("  后半是否 == 前半 =", K[:512] == K[512:])
print("  K[0:256] == K[256:512] ?", K[0:256] == K[256:512])
print("  K[0:256] == K[512:768] ?", K[0:256] == K[512:768])
# 是否"每 256 重复但每次旋转"
for rot in range(0, 256):
    if all(K[i] == K[i % 256] for i in range(1024)):
        print(f"  ★ K 是 256 字节周期（位移 {rot}）"); break

# ---------- 2. 载荷 A 里有没有 ASCII / UTF-16 串 ----------
def strings(buf, minlen=5, off=0):
    out = []
    for m in re.finditer(rb'[\x20-\x7e]{%d,}' % minlen, buf):
        out.append((off + m.start(), m.group()))
    return out

def wstrings(buf, minlen=5, off=0):
    out = []
    for m in re.finditer(rb'(?:[\x20-\x7e]\x00){%d,}' % minlen, buf):
        out.append((off + m.start(), m.group()[::2]))
    return out

print("\n### 2. 载荷A 的 ASCII 串（>=5，最多列 80 条）")
ss = strings(A, 5)
print("  总数 =", len(ss))
for off, s in ss[:80]:
    print(f"   {off:#08x}  {s[:90]!r}")

print("\n### 2b. 载荷A 的 UTF-16LE 串")
ws = wstrings(A, 5)
print("  总数 =", len(ws))
for off, s in ws[:20]:
    print(f"   {off:#08x}  {s[:80]!r}")

# ---------- 3. 载荷A 开头 512 字节 ----------
print("\n### 3. 载荷A 开头 512 字节（hex + ascii）")
for i in range(0, 512, 16):
    row = A[i:i+16]
    hx = " ".join(f"{b:02x}" for b in row)
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print(f"  {i:04x}  {hx}  |{asc}|")

# ---------- 4. 容器头 + 子表 ----------
print("\n### 4. 原始文件开头 96 字节")
for i in range(0, 96, 16):
    row = O[i:i+16]
    hx = " ".join(f"{b:02x}" for b in row)
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print(f"  {i:04x}  {hx}  |{asc}|")
