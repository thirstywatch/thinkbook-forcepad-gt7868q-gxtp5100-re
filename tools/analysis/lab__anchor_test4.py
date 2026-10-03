"""★★★ 关键复核：cont[0x122D+0xE40B] 与 anchor[0xF1+0xE40B] 连续 1026 B 相同 —— 真的吗？

位置换算：
  cont  偏移 = 0x0122D + 0x0E40B = 0x0F638
  anchor 偏移 = 0x000F1 + 0x0E40B = 0x0F4FC

0x0F638 落在【加扰区 0x1200-0x19800】内部！这是「加扰区里出现近 1 KiB 完全相同的字节」。

有两种解释：
  (i) 假阳性：这一段恰好是高重复数据（长 0 或长 FF），任何两份文件都能对上。
  (ii) 真信号：这一段是【厂商共用的常量表】，未被加扰。

必须把这段内容原样打出来看。若是高熵随机数据而仍逐字节相同，
那问题就变成「GT7868Q 与 GT9896 共用同一段未加扰数据」——对解 K 无直接帮助，
但需要记录。若是 0/FF 填充，则纯属噪声。
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


def show(tag, d, off, n=256):
    seg = d[off:off + n]
    print("  %s[0x%05X:%d] 熵=%.4f  0x00=%.1f%% 0xFF=%.1f%%" % (
        tag, off, n, ent(seg), 100 * seg.count(0) / len(seg), 100 * seg.count(255) / len(seg)))
    print("     HEX:", seg[:64].hex())
    print("     第二段HEX:", seg[64:128].hex())


print("=" * 78)
print("复核 A：那次「1026 B 相同」的原始位置")
print("=" * 78)
# 直接在 cont 里搜该段的前 24 字节（取自 anchor 0xF4FC）
probe = anchor[0x0F4FC:0x0F4FC + 24]
print("  探针 anchor[0x0F4FC:0x0F510] = %s" % probe.hex())
j = cont.find(probe)
print("  在 cont 中的位置：0x%05X" % j if j >= 0 else "  未找到")
if j >= 0:
    n = 0
    while j + n < len(cont) and 0x0F4FC + n < len(anchor) and cont[j + n] == anchor[0x0F4FC + n]:
        n += 1
    print("  实际连续相同长度 = %d B" % n)
    show("cont  ", cont, j)
    show("anchor", anchor, 0x0F4FC)
print()

print("=" * 78)
print("复核 B：去掉「长 0 / 长 FF」后，还有多少真实公共段？")
print("=" * 78)
SEG = 16
aset = {}
for i in range(0, len(anchor) - SEG):
    aset.setdefault(anchor[i:i + SEG], i)

real = []
for j in range(0x1200, min(0x19800, len(cont)) - SEG):
    k = cont[j:j + SEG]
    if k not in aset:
        continue
    # 排除高重复段（含单值占比>50% 的）
    c = collections.Counter(k)
    if c.most_common(1)[0][1] > SEG // 4:
        continue
    i = aset[k]
    n = 0
    while j + n < len(cont) and i + n < len(anchor) and cont[j + n] == anchor[i + n]:
        n += 1
    if n >= 16:
        real.append((n, j, i))

real = sorted(set(real), reverse=True)
print("  加扰区内「非重复模式」的 ≥16B 公共段：%d 个" % len(real))
for n, j, i in real[:15]:
    print("     长 %3d B  cont[0x%05X] == anchor[0x%05X]" % (n, j, i))
    print("          %s" % cont[j:j + min(n, 48)].hex())
    print("          熵=%.3f" % ent(cont[j:j + n]))
print()
if not real:
    print("  ⇒ 加扰区内不存在任何有意义的公共段。此前 2063B/1026B 全由长 0 区造成。")
