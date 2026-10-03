# -*- coding: utf-8 -*-
"""读外层 4×1084 B 明文配置记录 + 跨文件比对（项目最强方法 §4.5.2）"""
import struct, collections, os, difflib
d = open("bios-re/GT7868Q_native_fw.bin", 'rb').read()
R = [d[0x10 + i * 0x43C: 0x10 + (i + 1) * 0x43C] for i in range(4)]
print("=== 1. 4 条记录差异 ===")
r0 = R[0]
for i in range(1, 4):
    diff = [j for j in range(1084) if R[i][j] != r0[j]]
    print("  记录%d vs 记录0：差 %d 字节；差异偏移区间 %s" % (i, len(diff),
          ("0x%03X-0x%03X" % (diff[0], diff[-1])) if diff else "-"))
    if i == 1:
        print("     记录0 :", " ".join("%02x" % r0[j] for j in diff[:24]))
        print("     记录1 :", " ".join("%02x" % R[1][j] for j in diff[:24]))
print("  记录1 vs 记录2 / 3 差异:",
      sum(1 for j in range(1084) if R[1][j] != R[2][j]),
      sum(1 for j in range(1084) if R[1][j] != R[3][j]))

print()
print("=== 2. 明文配置区在记录内的位置（第一段可读区）===")
for base in (0x3C,):
    pass
print("  活体 0x96F8 读回 = 记录 +0x3C 起 30 B：", R[1][0x3C:0x3C + 30].hex(' '))

print()
print("=== 3. 关键数值搜索（BE u16 表内）===")
KEY = {"104/98 点击阈值?": [98, 104], "70/48 旧假设阈值": [70, 48],
       "90/100/120": [90, 100, 120], "字节 0x5A/0x64/0x78": None}
for i, r in enumerate(R):
    be = [int.from_bytes(r[j:j + 2], 'big') for j in range(0, 1082, 2)]
    c = collections.Counter(be)
    print("  记录%d: 70×%-3d 48×%-3d 90×%-3d 100×%-3d 120×%-3d  最高频值 %s"
          % (i, c[70], c[48], c[90], c[100], c[120], c.most_common(6)))

print()
print("=== 4. ★ 跨文件逐字节比对：外层记录 vs tpcfgsid*.cfg（项目最强方法）===")
CFG = {
    "sid0(Xiaomi7867)": "<WORKSPACE>",
    "sid2": "<WORKSPACE>",
    "sid3(LaiBao7986P)": "<WORKSPACE>",
}
cfgs = {}
for nm, p in CFG.items():
    if os.path.exists(p):
        cfgs[nm] = open(p, 'rb').read()
        print("  %-20s %d B" % (nm, len(cfgs[nm])))

def longest_common_runs(a, b, minlen=6):
    """找 a 中所有长度>=minlen 且出现在 b 中的连续片段"""
    res = []
    n = len(a)
    i = 0
    while i < n - minlen:
        best = 0
        for j in range(len(b) - minlen + 1):
            L = 0
            while i + L < n and j + L < len(b) and a[i + L] == b[j + L]:
                L += 1
            if L > best:
                best = L
        if best >= minlen:
            res.append((i, best))
            i += best
        else:
            i += 1
    return res

for nm, cb in cfgs.items():
    for i, r in enumerate(R):
        runs = longest_common_runs(r, cb, minlen=8)
        if runs:
            tot = sum(L for _, L in runs)
            print("  记录%d ↔ %-20s : %d 段，合计 %d B（记录长度 1084）"
                  % (i, nm, len(runs), tot))
            for off, L in runs[:6]:
                print("       记录+0x%03X 长 %3d : %s" % (off, L, r[off:off + min(L, 24)].hex(' ')))
        else:
            print("  记录%d ↔ %-20s : 无 ≥8 B 公共片段" % (i, nm))

print()
print("=== 5. 记录 vs 载荷A明文（是否同一套数据）===")
K = open("<WORKSPACE>", 'rb').read()
K316 = K[316:] + K[:316]
b = d
def parse(buf):
    for o in range(0, min(len(buf) - 300, 65536)):
        s = struct.unpack('>I', buf[o:o + 4])[0]
        if 1000 < s <= len(buf) - o and sum(buf[o + 6:o + 6 + s]) & 0xFFFF == struct.unpack('>H', buf[o + 4:o + 6])[0]:
            ent = []
            for i in range(30):
                q = o + 0x20 + i * 8
                t = buf[q]; ln = int.from_bytes(buf[q + 1:q + 5], 'big')
                if t == 0 and ln == 0: break
                ent.append((t, ln))
            return o, ent
    return None
o, ent = parse(b); off = o + 0x100
for i, (t, ln) in enumerate(ent):
    xr = b[off:off + ln]; off += ln
    x = bytes(v ^ K316[(k + 0x100) % 1024] for k, v in enumerate(xr))
    runs = longest_common_runs(x, R[1], minlen=8)
    if runs:
        tot = sum(L for _, L in runs)
        print("  载荷A块%-2d t=0x%02x 0x%05X ↔ 记录1 : %d 段 / %d B" % (i, t, ln, len(runs), tot))
        for o2, L in runs[:4]:
            print("       块内+0x%05X 长 %3d : %s" % (o2, L, x[o2:o2 + min(L, 24)].hex(' ')))
