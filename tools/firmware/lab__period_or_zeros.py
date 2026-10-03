# -*- coding: utf-8 -*-
"""自查：载荷A 明文的 16 字节周期 是真的记录结构，还是零串造成的假象？"""
import collections, math, struct, random

K = open("<WORKSPACE>", 'rb').read()
K316 = K[316:] + K[:316]
d = open("bios-re/GT7868Q_native_fw.bin", 'rb').read()


def parse(buf):
    for o in range(0, min(len(buf) - 300, 65536)):
        s = struct.unpack('>I', buf[o:o + 4])[0]
        if 1000 < s <= len(buf) - o and sum(buf[o + 6:o + 6 + s]) & 0xFFFF == \
                struct.unpack('>H', buf[o + 4:o + 6])[0]:
            ent = []
            for i in range(30):
                q = o + 0x20 + i * 8
                t = buf[q]
                ln = int.from_bytes(buf[q + 1:q + 5], 'big')
                if t == 0 and ln == 0:
                    break
                ent.append((t, ln))
            return o, ent
    return None


o, ent = parse(d)
off = o + 0x100
BL = []
for i, (t, ln) in enumerate(ent):
    xr = d[off:off + ln]
    off += ln
    BL.append((i, t, ln, bytes(v ^ K316[(k + 0x100) % 1024] for k, v in enumerate(xr))))


def mr(b, L):
    n = len(b) - L
    return sum(1 for i in range(n) if b[i] == b[i + L]) / n


print("=== 1. L profile (L=1..40): a real record period shows a LOCAL MAX at that L ===")
for (i, t, ln, x) in BL:
    if x.count(0) / ln > 0.6 or ln < 0x1000:
        continue
    prof = [(mr(x, L), L) for L in range(1, 41)]
    mx = max(prof)
    m16 = mr(x, 16)
    neigh = max(mr(x, 14), mr(x, 15), mr(x, 17), mr(x, 18))
    tag = "16 IS local max" if m16 > neigh else "16 NOT local max"
    print("  blk%-2d t=0x%02x: max L=%d (%.4f) | L=16: %.4f  neigh14/15/17/18 max=%.4f  %s"
          % (i, t, mx[1], mx[0], m16, neigh, tag))

print()
print("=== 2. CONTROL: shuffle each block by bytes (keep histogram, destroy structure) ===")
random.seed(0)
for (i, t, ln, x) in BL:
    if x.count(0) / ln > 0.6 or ln < 0x1000:
        continue
    obs = mr(x, 16)
    sh = []
    for _ in range(20):
        y = bytearray(x)
        random.shuffle(y)
        sh.append(mr(bytes(y), 16))
    m = sum(sh) / len(sh)
    sd = (sum((v - m) ** 2 for v in sh) / len(sh)) ** 0.5
    z = (obs - m) / sd if sd > 0 else 0
    tag = "REAL PERIOD" if z > 5 else "zero-run artifact"
    print("  blk%-2d t=0x%02x: obs L16=%.4f  shuffled %.4f+-%.4f  z=%+.1f  %s"
          % (i, t, obs, m, sd, z, tag))

print()
print("=== 3. how much of L=16 comes from zero runs ===")
for (i, t, ln, x) in BL:
    if x.count(0) / ln > 0.6 or ln < 0x1000:
        continue
    runs = []
    cur = 0
    for c in x:
        if c == 0:
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    tot = sum(runs)
    contrib = sum(max(0, r - 16) for r in runs)
    print("  blk%-2d: zero-runs=%d total-zero=%d ; L16 positions from runs>=16: %d (%.0f%% of zeros)"
          % (i, len(runs), tot, contrib, 100 * contrib / max(tot, 1)))
