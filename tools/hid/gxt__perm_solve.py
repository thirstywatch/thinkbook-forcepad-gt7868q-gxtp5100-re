#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
perm_solve.py —— 判定「位置置换层」是否存在、以及是否为固定置换

【前提（第十六轮已证）】
  tpfw.bin 中 10 个 1024 对齐的"完美均衡块"，每 256 值各恰好 4 次。
  tpfw[0x1C00:0x2000] == rot_left(K, 316)，K 是 Goodix 通用填充表。

【假设 H_perm】存储 = 在由 K 铺底的缓冲上，按固定置换 π 写入数据
  即: blk[i] = base[i] 其中 base 是 K 经过"某种位置重排"后的结果。
  若 π 固定，则**对多个均衡块求 π 应当得到同一个映射**。

【检验方法】
  对每个均衡块 blk 与参考块 ref=rot_left(K,316)：
    求多重集匹配 —— 因为均衡块里每个值出现 4 次，无法直接建立一一映射。
    ⇒ 改用**位置差异剖面**: d[i] = blk[i] - ref[i]，看 d 的分布是否比随机更集中。
       若 π 固定，d 应呈现「少数几个固定值」的强集中（因为大多数位置未动）。
  另：检查 ref 与 blk 的「相同位置命中率」。
      若置换 π 不动大部分位置，命中率应显著高于 1/256。

产出: perm_analysis.txt
"""
import os, math
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
TPFW = os.path.join(BASE, "tpfw_86272_PNOR_G1_7863.bin")
KFILE = os.path.join(BASE, "K_gt7868q.bin")
OUT = os.path.join(BASE, "cfg_parsed")
os.makedirs(OUT, exist_ok=True)

rep = []


def w(s=""):
    rep.append(s)
    print(s)


tpfw = open(TPFW, "rb").read()
K = open(KFILE, "rb").read()


def rot(x, n):
    return x[n:] + x[:n]


def ent(x):
    c = Counter(x)
    n = len(x)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


BAL = [0x1C00, 0x2000, 0x2400, 0x2800, 0x2C00, 0x9C00, 0xA000, 0xA400, 0xC400, 0x11400]
REF = rot(K, 316)

w("=" * 78)
w("位置置换层检验 —— 是否存在固定置换 π")
w("=" * 78)
w("参考块 REF = rot_left(K, 316)  (%d B)" % len(REF))

# ---- 检验 1: 相同位置命中率
w("\n【检验 1】各均衡块与 REF 的「相同位置命中率」")
w("-" * 78)
w("   %-10s %-8s %-8s %s" % ("块偏移", "命中数", "命中率", "判定"))
for off in BAL:
    blk = tpfw[off:off + 1024]
    same = sum(1 for i in range(1024) if blk[i] == REF[i])
    r = same / 1024.0
    verdict = "≈随机(1/256=0.0039)" if r < 0.02 else ("★显著" if r > 0.1 else "略高")
    w("   0x%05X   %-8d %.4f   %s" % (off, same, r, verdict))

# ---- 检验 2: 块与块之间的命中率（同一置换下应更高）
w("\n【检验 2】均衡块两两之间的「相同位置命中率」")
w("-" * 78)
w("   （若置换 π 固定且底层数据相同，块间命中率应显著高于 1/256）")
w("   %-10s %-10s %-8s %s" % ("块A", "块B", "命中率", "判定"))
pairs = []
for i in range(len(BAL)):
    for j in range(i + 1, len(BAL)):
        a = tpfw[BAL[i]:BAL[i] + 1024]
        b = tpfw[BAL[j]:BAL[j] + 1024]
        same = sum(1 for k in range(1024) if a[k] == b[k])
        r = same / 1024.0
        pairs.append((BAL[i], BAL[j], same, r))
pairs.sort(key=lambda x: -x[3])
for a, b, s, r in pairs[:10]:
    w("   0x%05X   0x%05X   %.4f   %s" % (a, b, r, "★高" if r > 0.05 else "低"))
w("   ...（共 %d 对，最高 %.4f，最低 %.4f，中位 %.4f）"
  % (len(pairs), pairs[0][3], pairs[-1][3], pairs[len(pairs) // 2][3]))

# ---- 检验 3: 差值剖面
w("\n【检验 3】d[i] = blk[i] - REF[i] 的分布集中度")
w("-" * 78)
for off in BAL[:6]:
    blk = tpfw[off:off + 1024]
    d = bytes((blk[i] - REF[i]) & 0xFF for i in range(1024))
    c = Counter(d)
    top = c.most_common(5)
    w("   0x%05X  distinct_d=%3d  H(d)=%.4f  top5=%s"
      % (off, len(c), ent(d), [(hex(k), v) for k, v in top]))

# ---- 检验 4: 是否 ref 只是 blk 的一个"多重集重排"（同分布检验）
w("\n【检验 4】多重集一致性（置换不改动多重集）")
w("-" * 78)
cb = Counter(REF)
for off in BAL:
    blk = tpfw[off:off + 1024]
    cc = Counter(blk)
    same_multiset = (cb == cc)
    diff = sum(abs(cb.get(k, 0) - cc.get(k, 0)) for k in set(cb) | set(cc))
    w("   0x%05X  多重集与 REF 相同? %-5s   差异计数 = %d" % (off, same_multiset, diff))

# ---- 检验 5: 直接尝试解置换（基于多重集 + 贪心位置保持）
w("\n【检验 5】能否构造固定置换 π 使 所有均衡块 = π(REF)")
w("-" * 78)
w("""
   方法：对每个均衡块，尝试求一个置换 π 满足 blk = [REF[π(i)]]；再验证
         同一个 π 是否同时满足所有 10 个块。
   可行性预判：由于每值出现 4 次，单个块存在 4!^256 种可能置换，
         但**跨 10 个块的联合约束**会迅速坍缩到唯一解（若 π 真存在）。
   本脚本用「位置-值」反查做首次坍缩：对每个块，记录
         候选 π 集合 = { i → j | REF[j] == blk[i] }
""")
# 联合约束求解
cands = None
for off in BAL:
    blk = tpfw[off:off + 1024]
    pos = {}
    for j, v in enumerate(REF):
        pos.setdefault(v, []).append(j)
    cur = []
    for i, v in enumerate(blk):
        cur.append(set(pos.get(v, [])))
    if cands is None:
        cands = cur
    else:
        cands = [cands[i] & cur[i] for i in range(1024)]

sizes = Counter(len(s) for s in cands)
w("   联合约束后，各位置候选数分布: %s" % dict(sorted(sizes.items())))
solved = sum(1 for s in cands if len(s) == 1)
w("   已唯一确定的位置: %d / 1024 (%.1f%%)" % (solved, 100.0 * solved / 1024))
if solved == 1024:
    pi = [next(iter(s)) for s in cands]
    w("   ★★★ 求出了唯一置换 π！")
    # 验证
    ok = all(bytes(REF[pi[i]] for i in range(1024)) == tpfw[o:o + 1024] for o in BAL)
    w("   验证 10 个块全部满足: %s" % ok)
    if ok:
        with open(os.path.join(OUT, "perm_pi.bin"), "wb") as f:
            f.write(bytes((p >> 8) & 0xFF for p in pi))
            f.write(bytes(p & 0xFF for p in pi))
        w("   π 已保存 -> cfg_parsed/perm_pi.bin  (1024 × u16BE)")
elif sizes.get(1, 0) > 500:
    w("   ⇒ 约束把大多数位置收敛到唯一，置换层**大概率存在**")
else:
    w("   ⇒ 约束未显著坍缩 ⇒ 各块使用的置换**不相同**，或底层数据也在变")
    w("     即: 不是「固定 π + 固定 REF」，而是「每块独立」")

with open(os.path.join(OUT, "perm_analysis.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
print("\n[done] -> cfg_parsed/perm_analysis.txt")
