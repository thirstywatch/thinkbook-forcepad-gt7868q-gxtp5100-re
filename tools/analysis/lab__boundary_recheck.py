"""★★★★★ 重新定界：GT7868Q 容器的【真实加扰边界】。

已确证的关键事实：
  cont[0x01238..] 与 GT9896 anchor[0x000FC..] 有 >2000 B 逐字节相同（熵 7.90）
  cont[0x05638..] 与 anchor[0x0F4FC..] 有 1026 B 逐字节相同（熵 6.93）

这直接【证伪】了「加扰区 0x1200-0x19800 全程加扰」的旧判断 ——
因为 0x1238 和 0x5638 都在该区间内，却与明文完全一致。

新假设：GT7868Q 容器 = GT9896 明文固件 + 尾部追加的 GT7868Q 专属段，
        而「加扰」只作用于其中某几段，或根本不作用于这些共有段。

本脚本重新做熵剖面 + 与 anchor 的逐段比对，给出【真实分段图】。
"""
import os
import collections
import math

W = r"<WORKSPACE>"
HERE = os.path.dirname(os.path.abspath(__file__))
cont = open(os.path.join(W, r"fw-touchpad\touchpad_GT7868Q_fw.bin"), "rb").read()
anchor = open(os.path.join(HERE, "goodix_gt9896_fw.bin"), "rb").read()


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    t = len(b)
    return -sum((v / t) * math.log2(v / t) for v in c.values())


print("cont=%d  anchor=%d\n" % (len(cont), len(anchor)))

print("=" * 96)
print("① GT7868Q 容器熵剖面（每 1 KiB）——『~8.0 = 乱码/加扰，<7.5 = 明文结构化』")
print("=" * 96)
for s in range(0, len(cont), 0x400):
    seg = cont[s:s + 0x400]
    if len(seg) < 256:
        break
    e = ent(seg)
    tag = "明文?" if e < 7.5 else ("中间" if e < 7.9 else "乱码")
    bar = "=" * max(0, int((e - 7.0) * 40))
    print("  0x%05X  熵=%.4f  %s %s" % (s, e, tag, bar))
