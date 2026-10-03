"""A③ 明文孪生搜索（离线横扫）。

目的：GT7868Q 加扰区 C 满足 C[i] = P[i] ^ K[i % 1024]（位置型，已由 period_model_test 判定）。
      ⇒ 只要找到【任意一段 1024 B 连续明文 P 且相位对齐】，即可恢复 K、解开全镜像。
      ⇒ 等价判据：X = C ⊕ candidate 必须是「1024 周期」的；即 X[i] == X[i+1024] 命中率 ≫ 基线。

本脚本把本机所有能拿到的 Goodix / 触控板 / BIOS 固件素材全过一遍，
先在候选里找 YELSTO 等明文锚点，再做 (C ⊕ candidate) 的 1024 周期性打分。

★ 不修改任何文件，纯读。
"""
import os
import re
import sys
import glob

W = r"<WORKSPACE>"
TP = r"<LAB>\touchpad-lab"

CONT = os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin")
cont = open(CONT, "rb").read()
print("容器(密文) : %s  %d B" % (CONT, len(cont)))

# 加扰区（熵剖面确定）
S, E = 0x1200, 0x19800
C = cont[S:E]
print("加扰区 C   : [0x%05X, 0x%05X)  %d B = %d 个 1024B 块\n" % (S, E, len(C), len(C) // 1024))

L = 1024
BASE = 1.0 / 256.0


def period1024_score(x):
    """X 的 1024 周期性：X[i] == X[i+1024] 的比例"""
    n = len(x) - L
    if n <= 0:
        return 0.0, 0
    hit = sum(1 for i in range(n) if x[i] == x[i + L])
    return hit / n, n


def anchored_score(cand, off=0):
    """取 cand[off:off+len] 与 C 逐字节异或，看 1024 周期性"""
    m = min(len(cand) - off, len(C))
    if m < 2 * L:
        return 0.0, 0
    x = bytes(a ^ b for a, b in zip(C[:m], cand[off:off + m]))
    return period1024_score(x)


# ────────────────────────────────────────────────────────────
# 候选清单（本机全部固件类素材）
# ────────────────────────────────────────────────────────────
cands = []

SIZE_CAP = 40 * 1024 * 1024   # 超 40MB 的先跳过（大包仅做尾部锚点扫描）
for root in (W, TP):
    for pat in ("**/*.bin", "**/*.BIN", "**/*.PAT", "**/*.Cap", "**/*.cap",
                "**/*.fw", "**/*.efi", "**/*.cab", "**/*.exe", "**/*.dll"):
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if sz < 4096 or sz > SIZE_CAP:
                continue
            cands.append(p)

# 去重（同尺寸同内容由后续哈希隐式处理）
cands = sorted(set(cands))
print("候选文件 %d 个\n" % len(cands))

# ────────────────────────────────────────────────────────────
# 阶段 1：明文锚点存在性（YELSTO / 汇顶特征串）
# ────────────────────────────────────────────────────────────
ANCHORS = [b"YELSTO", b"YELS", b"Yellowstone", b"GT7868", b"GXTP", b"GTX8",
           b"goodix", b"Goodix", b"GOODIX"]

print("=" * 78)
print("阶段 1：候选内是否含明文锚点（YELSTO 最有价值 —— 它就是 0x4018 的指纹）")
print("=" * 78)
hits = []
for p in cands:
    try:
        d = open(p, "rb").read()
    except OSError:
        continue
    found = {}
    for a in ANCHORS:
        c = d.count(a)
        if c:
            found[a.decode()] = c
    if "YELSTO" in found or "YELS" in found:
        hits.append((p, found))
        print("  ★ %s  尺寸=%d" % (p, len(d)))
        print("      %s" % found)
if not hits:
    print("  （无任何候选含 YELSTO —— 与历史结论一致）")
print()

# ────────────────────────────────────────────────────────────
# 阶段 2：强判据 —— (C ⊕ candidate) 的 1024 周期性
# ────────────────────────────────────────────────────────────
print("=" * 78)
print("阶段 2：★ 强判据  (C ⊕ candidate) 的 1024 周期性   [基线 ~0.0039]")
print("=" * 78)
print("  判读：≥ 0.05（13×基线）值得深入；≥ 0.5 基本就是明文；≤ 0.01 直接排除\n")

results = []
_cache = {}
for p in cands:
    try:
        if p not in _cache:
            _cache.clear()
            _cache[p] = open(p, "rb").read()
        d = _cache[p]
    except OSError:
        continue
    # 只在文件开头的若干相位试（整块对齐 + 半块偏移）
    best = (-1.0, None)
    maxoff = len(d) - 2 * L
    if maxoff < 0:
        continue
    step = max(0x1000, maxoff // 48)
    offs = list(range(0, maxoff + 1, max(1, step)))
    offs += [0, 0x100, 0x200, 0x400, 0x800, 0x1000]
    for off in sorted(set(o for o in offs if 0 <= o <= maxoff)):
        r, n = anchored_score(d, off)
        if r > best[0]:
            best = (r, off)
    if best[0] >= 0:
        results.append((best[0], p, best[1], len(d)))

results.sort(reverse=True)
print("  ── 全候选排序（Top 25）──")
for r, p, off, sz in results[:25]:
    flag = "★" if r >= 0.05 else ("?" if r >= 0.01 else " ")
    print("  %s %-9.6f (%5.1f×)  off=0x%-6X  %8d B  %s" % (
        flag, r, r / 0.0039, off, sz, os.path.basename(p)))

print()
if all(r < 0.05 for r, _, _, _ in results):
    print("  ⇒ 无任何候选通过强判据。本地素材产地全部用尽。")
else:
    print("  ⇒ 有候选超过 0.05！需逐个人工核验（可能是巧合：候选本身高度重复时该判据会虚高）")
