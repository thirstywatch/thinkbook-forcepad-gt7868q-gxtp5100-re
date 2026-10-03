# diff_snap.py —— 对比两次 16 位空间全段快照（snapA/snapB），找出点按期间发生变化的地址
# 用法: python diff_snap.py snapA.txt snapB.txt
import sys, re

def load(p):
    d = {}
    for line in open(p, encoding='utf-8'):
        line = line.strip()
        m = re.match(r'^0x([0-9A-Fa-f]{4})\s+(.*)$', line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        body = m.group(2)
        if body.startswith('ERR'):
            continue
        bs = [int(x, 16) for x in body.split()]
        for i, b in enumerate(bs):
            d[addr + i] = b
    return d

a = load(sys.argv[1])
b = load(sys.argv[2])
keys = sorted(set(a) & set(b))
diff = [k for k in keys if a[k] != b[k]]
print('共同地址 %d 个，其中变化 %d 个' % (len(keys), len(diff)))
if not diff:
    print('⇒ 点按期间主机可读空间【完全没有任何字节变化】')
    sys.exit(0)

# 按连续段聚合
runs = []
s = diff[0]; prev = diff[0]
for k in diff[1:]:
    if k == prev + 1:
        prev = k
    else:
        runs.append((s, prev)); s = k; prev = k
runs.append((s, prev))
runs.sort(key=lambda r: -(r[1] - r[0]))
print('\n变化段（按长度排序，前 25 段）:')
for s, e in runs[:25]:
    n = e - s + 1
    seg_a = ' '.join('%02X' % a[k] for k in range(s, e + 1))
    seg_b = ' '.join('%02X' % b[k] for k in range(s, e + 1))
    print('  0x%04X..0x%04X (%2d B)  A: %s' % (s, e, n, seg_a[:70]))
    print('  %-18s          B: %s' % ('', seg_b[:70]))
print('\n共 %d 段' % len(runs))
# 按地址区间归类统计
buckets = {}
for k in diff:
    pg = k >> 12
    buckets[pg] = buckets.get(pg, 0) + 1
print('\n按 4KB 页统计变化字节数:')
for pg in sorted(buckets):
    print('  0x%04X 页: %d 字节' % (pg << 12, buckets[pg]))

# ── 找"计数器/触发寄存器"候选：B 比 A 恰好增大一个小量的 16/32 位小端值 ──
print('\n=== 计数器候选（u16/u32 小端，0 < Δ ≤ 4096） ===')
cands = []
for k in keys:
    if k + 2 <= max(keys):
        v16a = a.get(k, 0) | (a.get(k + 1, 0) << 8)
        v16b = b.get(k, 0) | (b.get(k + 1, 0) << 8)
        d = v16b - v16a
        if 0 < d <= 4096:
            cands.append((k, 2, v16a, v16b, d))
    if k + 4 <= max(keys):
        v32a = sum(a.get(k + i, 0) << (8 * i) for i in range(4))
        v32b = sum(b.get(k + i, 0) << (8 * i) for i in range(4))
        d = v32b - v32a
        if 0 < d <= 4096:
            cands.append((k, 4, v32a, v32b, d))
# 同一地址只留一个（优先 16 位）
seen = {}
for k, w, va, vb, d in cands:
    seen.setdefault(k, (w, va, vb, d))
top = sorted(seen.items(), key=lambda kv: -kv[1][3])[:40]
for k, (w, va, vb, d) in top:
    print('  0x%04X u%d  %d -> %d  (Δ=%d)' % (k, w * 8, va, vb, d))
print('  共 %d 个候选地址' % len(seen))
