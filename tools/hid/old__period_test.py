"""决定性检验：密文里是否存在【字节级周期】。
  · 周期加扰(C[i]=P[i]^K[i mod L0])下，明文里的常量段会让 C[i]==C[i+L0] 大量成立
    => 相等率在 L0 及其倍数处出现尖峰
  · 强密码(C[i]=P[i]^keystream[i])下，任何 L 的相等率都 ≈ 1/256
同时输出 MD5 确认两份容器是否同一份。
"""
import os, hashlib, random

D = r"<WORKSPACE>"
for f in ("gt7868q.bin", "touchpad_GT7868Q_fw.bin"):
    p = os.path.join(D, f)
    h = hashlib.md5(open(p, "rb").read()).hexdigest()
    print("%-28s md5=%s" % (f, h))

d = open(os.path.join(D, "touchpad_GT7868Q_fw.bin"), "rb").read()
seg = d[0x1400:0x19A00]
n = len(seg)
print("\n段长 =", n)

def eqrate(data, L):
    a = data[:n - L]
    b = data[L:]
    eq = sum(1 for x, y in zip(a, b) if x == y)
    return eq / len(a)

# 对照：打乱
rnd = bytearray(seg); random.seed(5); random.shuffle(rnd); rnd = bytes(rnd)

print("\n%-6s %-12s %-12s %s" % ("L", "真数据相等率", "打乱对照", "倍数/判定"))
for L in (2, 3, 4, 5, 6, 7, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048):
    r = eqrate(seg, L)
    c = eqrate(rnd, L)
    dev = (r - c) / c * 100 if c else 0
    flag = "★ 尖峰" if dev > 15 else ""
    print("%-6d %-12.5f %-12.5f %+7.1f%%  %s" % (L, r, c, dev, flag))

# 找出"重复 16 字节块"出现的位置间隔
import collections
seen = collections.defaultdict(list)
for i in range(0, n - 15, 16):
    seen[seg[i:i + 16]].append(i)
top = sorted(seen.items(), key=lambda kv: -len(kv[1]))[:5]
print("\n=== 最高频 16 字节块的出现位置 ===")
for blk, offs in top:
    gaps = [offs[k + 1] - offs[k] for k in range(len(offs) - 1)]
    print("  出现 %2d 次  gaps=%s" % (len(offs), gaps[:14]))
