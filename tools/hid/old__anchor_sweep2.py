"""A③ 明文孪生搜索 —— 第二轮：给「强判据」加上自校准，消除假阳性。

问题：上一轮 anchor_sweep.py 的 Top25 全是低熵/高重复候选（IhisiSmm.bin、
      FmpUpdateDxe.bin、N4C_*_blob*.bin 等）。原因很直接：
      若候选本身有大量重复字节，C ⊕ candidate 也会跟着"重复"，
      1024-自同一性自然虚高 —— 这是判据的假阳性通道。

修正：对每个 (candidate, offset) 计算两个量
      r_obs = X[i]==X[i+1024] 的观测比例   （X = C ⊕ cand_seg）
      r_null = cand_seg 自身的 1024-自同比例（无 C 的对照）
      ★ 真正有信号的判据是 r_obs 显著高于 r_null，而不是 r_obs 高。
      另外要求 X 的熵接近 8.0（K 应是随机的，不是常量填充）。

再补一条正交证据：若 candidate 真是明文，则 X = K 在不同 offset 下
      应该「换相位就变」但「同一相位跨文件稳定」——本轮不做多文件，
      只做自校准 + 熵过滤，先筛掉噪声。
"""
import os
import glob

W = r"<WORKSPACE>"
TP = r"<LAB>\touchpad-lab"
CONT = os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin")
cont = open(CONT, "rb").read()

S, E = 0x1200, 0x19800
C = cont[S:E]
L = 1024


def rep_rate(x):
    n = len(x) - L
    if n <= 0:
        return 0.0
    return sum(1 for i in range(n) if x[i] == x[i + L]) / n


def ent(b):
    import collections, math
    if not b:
        return 0.0
    c = collections.Counter(b)
    t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


SIZE_CAP = 40 * 1024 * 1024
cands = []
for root in (W, TP):
    for pat in ("**/*.bin", "**/*.BIN", "**/*.PAT", "**/*.Cap", "**/*.cap",
                "**/*.fw", "**/*.efi", "**/*.cab", "**/*.exe", "**/*.dll"):
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if 4096 <= sz <= SIZE_CAP:
                cands.append(p)
cands = sorted(set(cands))

print("=" * 82)
print("★ 自校准判据：delta = r_obs(C⊕cand) − r_null(cand自同)   且 熵(X) ≥ 7.5")
print("   （delta 显著为正 + 高熵 ⇒ 真有位置型 keystream 或真有周期结构）")
print("=" * 82)
print("   %-10s %-10s %-10s %-8s  %s" % ("delta", "r_obs", "r_null", "熵(X)", "候选"))
print("-" * 82)

rows = []
for p in cands:
    try:
        d = open(p, "rb").read()
    except OSError:
        continue
    maxoff = len(d) - 2 * L
    if maxoff < 0:
        continue
    step = max(0x1000, maxoff // 24)
    offs = sorted(set(list(range(0, maxoff + 1, max(1, step))) +
                      [0, 0x100, 0x200, 0x400, 0x800, 0x1000]))
    best = None
    for off in offs:
        if not (0 <= off <= maxoff):
            continue
        seg = d[off:off + len(C)]
        r_null = rep_rate(seg)
        x = bytes(a ^ b for a, b in zip(C[:len(seg)], seg))
        r_obs = rep_rate(x)
        ex = ent(x)
        delta = r_obs - r_null
        if best is None or delta > best[0]:
            best = (delta, r_obs, r_null, ex, off)
    if best:
        rows.append((best[0], p, best))

rows.sort(reverse=True)
for delta, p, (_, r_obs, r_null, ex, off) in rows[:20]:
    flag = "★" if (delta > 0.02 and ex >= 7.5) else " "
    print("  %s %-10.6f %-10.6f %-10.6f %-8.4f  %s @0x%X" % (
        flag, delta, r_obs, r_null, ex, os.path.basename(p), off))

print()
survivors = [(d, p) for d, p, b in rows if d > 0.02 and b[3] >= 7.5]
print("通过「delta>0.02 且 熵≥7.5」的候选：%d 个" % len(survivors))
for d, p in survivors:
    print("   ★★ %.6f  %s" % (d, p))
if not survivors:
    print("   （无 —— 本地素材在自校准判据下全部排除）")
