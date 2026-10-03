"""8051 语义检验：GT7868Q 主体是「Turbo 51 代码」还是「数据」？

已确认架构 = Turbo 51（增强型 8051，见 GT911 数据手册框图 + 官方源码 xdata/16 位地址）。

判据设计（8051 专有，比操作码频率强得多）：
 A1 LCALL(0x12)/LJMP(0x02)/MOV DPTR,#imm16(0x90) 后的 16 位地址分布
    —— 真代码：目标集中在 code 空间且成簇；数据：均匀铺满 0..0xFFFF
 A2 4 KiB「代码块」内的地址簇聚度
 A3 跳转目标落在「已知指令边界」的比例（用指令长度表推进）
 A4 对照 TF100A（ARM 代码）与随机字节

8051 指令长度表（仅需长度，用于边界推进）：
  3 字节: 02 12 90 75 85 B4-BF(除B8-BF为3) B5 D5 43 53 63
  2 字节: 其余大部分（含 x4/x5/x6/x7 立即数类、01/21/..(x1) AJMP、C0 C5 D0 D8-DF E5 F5 等）
  1 字节: 其余
"""
import os
import collections

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
GQ = d[0x1200:0x19800]
TF = d[0x19800:]


def build_len_table():
    """8051 指令长度表（256 项）。默认 1 字节，再修正 2/3 字节。"""
    L = [1] * 256
    # 2 字节：立即数/直接地址/相对跳转
    for op in (0x24, 0x25, 0x34, 0x35, 0x44, 0x45, 0x54, 0x55, 0x64, 0x65, 0x74, 0x75,
               0x76, 0x77, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F,
               0x05, 0x15, 0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80,
               0x90, 0xB0, 0xA0, 0xC0, 0xD0, 0xE5, 0xF5,
               0xC5, 0x86, 0x87, 0x96, 0x97, 0xA6, 0xA7, 0xB6, 0xB7,
               0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF,
               0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF,
               0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
               0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
               0xD8, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF,
               0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF,
               0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F,
               0x98, 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F,
               0x82, 0x83, 0x92, 0x93, 0xA2, 0xA3, 0xB2, 0xB3,
               0xC2, 0xC3, 0xD2, 0xD3, 0x72, 0x73, 0x62, 0x63,
               0xE6, 0xE7, 0xF6, 0xF7, 0xC6, 0xC7, 0xD6, 0xD7,
               0x04, 0x14, 0x06, 0x16):
        L[op] = 2
    # 3 字节
    for op in (0x02, 0x12, 0x90, 0x75, 0x85, 0x43, 0x53, 0x63, 0xB5, 0xD5,
               0xB4, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF):
        L[op] = 3
    # 修正：以上把若干 op 设为 2 又设 3，以 3 为准（顺序保证）
    for op in (0x40, 0x50, 0x60, 0x70, 0x80, 0x05, 0x15, 0x10, 0x20, 0x30):  # rel/direct 类为 2
        L[op] = 2
    # AJMP x1 / ACALL x1：0x01,0x11,...,0xF1 均为 2 字节
    for h in range(16):
        L[(h * 0x10 + 0x01) & 0xFF] = 2
    L[0x11] = 2
    return L


LEN = build_len_table()
print("8051 指令长度表：1B %d 个, 2B %d 个, 3B %d 个" % (
    LEN.count(1), LEN.count(2), LEN.count(3)))
print()


def target_addr_stats(seg, label):
    """收集 0x12/0x02/0x90 后的 16 位目标地址，看分布"""
    tgts = []
    for i in range(len(seg) - 2):
        if seg[i] in (0x12, 0x02, 0x90):
            hi = seg[i + 1]
            lo = seg[i + 2]
            tgts.append((hi << 8) | lo)
    if not tgts:
        print("  %-14s 无候选" % label)
        return None
    c = collections.Counter(t >> 12 for t in tgts)      # 高 4 位分桶
    n = len(tgts)
    # 簇聚度：最高 3 个桶占比
    top3 = sum(v for _, v in c.most_common(3)) / n
    print("  %-14s 候选 %5d 个；高4位分桶 Top6: %s；Top3 占比 %.1f%%" % (
        label, n, c.most_common(6), 100 * top3))
    return tgts


print("=" * 100)
print("A1 跳转/装载目标地址分布（0x12 LCALL / 0x02 LJMP / 0x90 MOV DPTR）")
print("=" * 100)
t_gq = target_addr_stats(GQ, "GT7868Q主体")
t_tf = target_addr_stats(TF, "TF100A(ARM)")
import random
random.seed(4)
t_rn = target_addr_stats(bytes(random.randrange(256) for _ in range(len(GQ))), "随机字节")
print()

print("=" * 100)
print("A2 均匀性检验（真代码应显著偏离均匀；数据接近均匀）")
print("=" * 100)
for label, tgts in (("GT7868Q主体", t_gq), ("TF100A(ARM)", t_tf), ("随机字节", t_rn)):
    if not tgts:
        continue
    c = collections.Counter(t >> 12 for t in tgts)
    n = len(tgts)
    chi = sum((c.get(k, 0) - n / 16) ** 2 / (n / 16) for k in range(16))
    print("  %-14s 16 桶卡方 = %8.1f  (均匀期望 ≈15；越大越集中)" % (label, chi))
print()

print("=" * 100)
print("A3 指令边界推进：目标地址是否落在「用长度表推出的指令起点」上")
print("=" * 100)


def boundary_hit(seg, tgts):
    # 从 0 开始按长度表推进，收集所有可能的指令起点
    starts = set()
    p = 0
    while p < len(seg):
        starts.add(p)
        p += LEN[seg[p]]
    hit = sum(1 for t in tgts if t < len(seg) and t in starts)
    return hit / max(1, len(tgts)), len(starts) / len(seg)


for label, seg, tgts in (("GT7868Q主体", GQ, t_gq), ("TF100A(ARM)", TF, t_tf)):
    if not tgts:
        continue
    r, dens = boundary_hit(seg, tgts)
    print("  %-14s 命中率 %.4f   指令起点密度 %.4f   随机期望 ≈ %.4f" % (
        label, r, dens, dens))
print()

print("=" * 100)
print("A4 结论判读")
print("=" * 100)
print("  · 若 GT7868Q 主体的目标地址「均匀铺满 0..0xFFFF」且桶卡方 ≈15 ⇒ 不是代码")
print("  · 若显著成簇（卡方远大于 15）且边界命中率高于随机 ⇒ 是代码")
