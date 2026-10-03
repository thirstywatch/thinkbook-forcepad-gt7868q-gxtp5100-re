"""决胜实验：X9-15 BIOS 里的 Flash_B06D0.PAT（99,328 B）是不是容器加扰区的【明文】？

判据（强判据，不是"看起来像"）：
  若 PAT == 明文 P，则 X = C ^ PAT = K 必然是【周期 1024 的位置型 keystream】
  ⇒ X[i] == X[i+1024] 的比例应极高（接近 1.0），而随机基线只有 0.39%。
  反之若 PAT 无关，X 无任何 1024 周期性。
"""
import os, collections, math, re

W = r"<WORKSPACE>"
cont = open(os.path.join(W, "fw-touchpad", "touchpad_GT7868Q_fw.bin"), "rb").read()

def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())

def show(name, d):
    print("=== %s : %d B  熵=%.4f  0x00=%.2f%%  0xFF=%.2f%% ===" % (
        name, len(d), ent(d), 100.0 * d.count(0) / len(d), 100.0 * d.count(0xFF) / len(d)))
    print("  首 64B:", " ".join("%02X" % x for x in d[:64]))
    print("  ASCII :", "".join(chr(x) if 32 <= x < 127 else "." for x in d[:64]))
    ss = re.findall(rb"[\x20-\x7e]{8,}", d)
    print("  可打印串(>=8) %d 条，前 8：" % len(ss))
    for s in ss[:8]:
        print("     ", s.decode('latin-1')[:70])

for fn in ("Flash_B06D0.PAT", "Flash_B06D1.PAT"):
    p = os.path.join(W, "x9bios", "iso_fat", fn)
    d = open(p, "rb").read()
    show(fn, d)
    print()

print("=" * 70)
print("★ 核心判据：X = C[offset:offset+len(PAT)] ^ PAT  的 1024 周期性")
print("   若 PAT 是明文 ⇒ 1024 周期一致性应 ≫ 基线 (0.0039)\n")

for fn in ("Flash_B06D0.PAT", "Flash_B06D1.PAT"):
    pat = open(os.path.join(W, "x9bios", "iso_fat", fn), "rb").read()
    lp = len(pat)
    best = []
    for off in range(0, 0x20000, 0x200):
        if off + lp > len(cont):
            break
        x = bytes(a ^ b for a, b in zip(cont[off:off + lp], pat))
        hit = sum(1 for i in range(lp - 1024) if x[i] == x[i + 1024])
        tot = lp - 1024
        best.append((hit / tot, off, ent(x)))
    best.sort(reverse=True)
    print("--- %s ---" % fn)
    for r, off, e in best[:6]:
        print("   offset=0x%05X  1024周期一致性=%.6f (%.1f×基线)  异或后熵=%.4f" % (
            off, r, r / 0.0039, e))
    print()

# 另外：PAT 与容器是否有任何直接相关性
print("=== PAT 与容器各段的直接相关性 ===")
for fn in ("Flash_B06D0.PAT", "Flash_B06D1.PAT"):
    pat = open(os.path.join(W, "x9bios", "iso_fat", fn), "rb").read()
    for name, seg in (("cont[0:0x1400]", cont[0:0x1400]),
                      ("cont[0x1400:0x19800]", cont[0x1400:0x19800]),
                      ("cont[0x19A00:]", cont[0x19A00:])):
        n = min(len(pat), len(seg))
        eq = sum(1 for i in range(n) if pat[i] == seg[i]) / n
        print("   %-22s vs %-20s 相等率 %.4f (%.1f/256)" % (fn, name, eq, eq * 256))
