#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_5a_struct.py —— 判定 tpcfgsid*.cfg 中的 0x5A 到底是「I2C 从地址」还是「普通参数字节」

判据（多假设互斥检验）:
  H1  I2C 从地址（AW86927）→ 必须成对出现「写地址 0x5A + 读地址 0x5B」，且紧跟寄存器地址
  H2  普通参数字节 → 分布随机，不构成「地址+寄存器+长度」三段式

做法:
  1. 统计三个 cfg 中 0x5A / 0x5B 的出现次数与位置
  2. 在 0x5A 周围 ±16 字节内检查是否出现 0x5B 或 (0x5A+1)
  3. 检查 0x5A 后第 1 字节是否像 I2C 寄存器地址（0x00-0xFF 都可能，故看是否有重复模式）
  4. 与「控制组」：统计其他高频字节（0x50, 0x80, 0x00, 0x1E）的出现次数作对比
"""
import os, sys
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
CFGD = os.path.join(BASE, "cfg")
FILES = {
    "sid0": "tpcfgsid0_Xiaomi7867_20240307.cfg.txt",
    "sid2": "tpcfgsid2_20230407.cfg.txt",
    "sid3": "tpcfgsid3_LaiBao7986P_20220701.cfg.txt",
}


def load(name):
    with open(os.path.join(CFGD, FILES[name]), encoding="utf-8") as f:
        toks = [t.strip() for t in f.read().split(",") if t.strip()]
    return [int(t, 16) for t in toks if t.lower().startswith("0x")]


report = []
print("=" * 78)
print("0x5A / 0x5B 结构检验")
print("=" * 78)

for tag in ("sid0", "sid2", "sid3"):
    b = load(tag)
    cnt = Counter(b)
    n_5a = cnt[0x5A]
    n_5b = cnt[0x5B]
    print("\n### %s  (size=%d)" % (tag, len(b)))
    print("    0x5A 出现 %d 次   0x5B 出现 %d 次" % (n_5a, n_5b))
    print("    通用高频字节对照: 0x00=%d  0x80=%d  0x50=%d  0x1E=%d  0x28=%d  0x64=%d"
          % (cnt[0x00], cnt[0x80], cnt[0x50], cnt[0x1E], cnt[0x28], cnt[0x64]))

    # 找 5A 与 5B 的最近距离
    pa = [i for i, v in enumerate(b) if v == 0x5A]
    pb = [i for i, v in enumerate(b) if v == 0x5B]
    if pa and pb:
        for i in pa:
            near = min(abs(i - j) for j in pb)
            print("    @%04X  最近 0x5B 距离 = %d" % (i, near))
    else:
        print("    (无双地址共存)" if not pb else "")

    # 假设 H1: 若为 I2C 从地址，写地址与读地址应成对且相邻（常见 |7bit<<1|）
    # 常见形式: 5A 05 => 0x5A 后跟寄存器号
    # 检验 0x5A 后一字节的分布
    after = Counter(b[i + 1] for i in pa if i + 1 < len(b))
    before = Counter(b[i - 1] for i in pa if i > 0)
    print("    5A 后一字节分布: %s" % dict(after.most_common(6)))
    print("    5A 前一字节分布: %s" % dict(before.most_common(6)))

    # 检验 0x5A 是否出现在「等差/固定间隔」位置（数据表特征）
    if len(pa) > 2:
        diffs = [pa[i + 1] - pa[i] for i in range(len(pa) - 1)]
        print("    5A 位置间隔: %s" % diffs)

print("\n" + "=" * 78)
print("结论判据")
print("=" * 78)
print("""
- 若 0x5A 与 0x5B 在同一 cfg 内共存且距离 <=8，且 0x5A 后紧跟一个低位寄存器号
  → 支持 H1（I2C 从地址对）。
- 若 0x5A 出现在长数值序列中间（前後都是 u16 参数），且 0x5B 从不出现
  → 支持 H2（普通参数字节），此前把它当 I2C 地址是**过度解读**。
- 对照组: 0x5A 的频次若与 0x50/0x28 等参数值同量级，则更偏向 H2。
""")
