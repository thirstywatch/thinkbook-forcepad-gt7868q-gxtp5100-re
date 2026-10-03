"""★★ 关键实验：用 GT9896 与本机容器中【逐字节完全相同】的配置表作为已知明文锚点。

发现：cont[0x0116C] 与 anchor[0x00030] 有完全相同的长序列
      03 00 00 20 00 00 60 00 03 00 00 20 00 00 80 00 ...
      （这是 GTX8 的「16 位地址/长度对」配置表，两家共用）

但它落在【本机明文段】（0x1142 附近），所以它不能用来解加扰区。
真正要问的是：同类结构在【加扰区】里有没有？若有，且明文来自 GT9896，就是锚点。

本脚本：
  A. 精确测定 cont[0x0116C] / anchor[0x00030] 的公共串长度
  B. 在【加扰区 0x1200-0x19800】里找是否也有类似配置表结构（用 1024 相位一致性定位）
  C. 对每个 anchor 偏移做「局部窗口」强判据（1 KiB 窗口，而非全段），
     因为只要 1 KiB 连续明文就够
"""
import os

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()

print("=" * 78)
print("A. 两固件在「配置表区」的公共串长度")
print("=" * 78)


def lcs_at(a, ia, b, ib, cap=4096):
    n = 0
    while n < cap and ia + n < len(a) and ib + n < len(b) and a[ia + n] == b[ib + n]:
        n += 1
    return n


pairs = [(0x0116C, 0x00030), (0x0000C, 0x00084), (0x01142, 0x00006)]
for ia, ib in pairs:
    n = lcs_at(cont, ia, anchor, ib)
    print("  cont[0x%05X] vs anchor[0x%05X]  连续相同 %d B" % (ia, ib, n))
    if n >= 16:
        print("     ", cont[ia:ia + min(n, 64)].hex())
print()

# 找全部「公共 16 字节以上」的块（不要求对齐）
print("=" * 78)
print("B. 全部 ≥16 B 的公共串（去重，找最长）")
print("=" * 78)
SEG = 16
seen = {}
for i in range(0, len(anchor) - SEG):
    seen.setdefault(anchor[i:i + SEG], []).append(i)
found = {}
for j in range(0, len(cont) - SEG):
    k = cont[j:j + SEG]
    if k in seen:
        i = seen[k][0]
        n = lcs_at(cont, j, anchor, i)
        found.setdefault(n, (j, i, k))
for n in sorted(found, reverse=True)[:12]:
    j, i, k = found[n]
    zone = "明文段" if j < 0x1200 else ("加扰区" if j < 0x19800 else "TF100A段")
    print("  长 %3d B  cont[0x%05X](%s) == anchor[0x%05X]" % (n, j, zone, i))
    print("        %s" % cont[j:j + min(n, 48)].hex())
print()

# ── C. 局部 1 KiB 窗口强判据 ──
print("=" * 78)
print("C. 局部窗口强判据：对每个 anchor 起点，取 1 KiB 试 X = C[win] ^ anchor[off]")
print("   只要窗口内 1024 周期一致（需 ≥2 KiB 才可测）——改为测「X 的自重复」")
print("=" * 78)
S, E = 0x1200, 0x19800
C = cont[S:E]
L = 1024


def rep(x):
    n = len(x) - L
    if n <= 0:
        return 0.0, 0
    return sum(1 for i in range(n) if x[i] == x[i + L]) / n, n


rows = []
for off in range(0, max(1, len(anchor) - 0x8000), 0x200):
    seg = anchor[off:off + 0x8000]
    if len(seg) < 0x4000:
        break
    # 用加扰区开头 32 KiB
    x = bytes(a ^ b for a, b in zip(C[:len(seg)], seg))
    r, n = rep(x)
    rows.append((r, off, n))
rows.sort(reverse=True)
print("   %-12s %-8s %s" % ("一致性", "倍数", "anchor 偏移"))
for r, off, n in rows[:10]:
    print("   %-12.6f %-8.1f anchor[0x%05X]  (n=%d)" % (r, r / 0.0039, off, n))
print()

# 随机对照：打乱 anchor 再测
import random
random.seed(7)
sh = bytearray(anchor[:0x8000])
random.shuffle(sh)
xr = bytes(a ^ b for a, b in zip(C[:0x8000], bytes(sh)))
rr, _ = rep(xr)
print("   随机对照（打乱 anchor） 一致性=%.6f  ⇒ 上表若接近此值即无信号" % rr)
