#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_5a_ref.py —— 用「引用完整性」判据复核 0x5A 的三段式是否真的是 I2C 写序列

三段式 (sid3 @0x0146 / @0x015E):
    len=04 | dev=5A | 00 00 00 | reg=50 | dev=5A | 00 00 00 | cmd=03
两种解读：
  H_A  I2C 写序列: [len][dev 0x5A][00 00 00 pad][reg 0x50][dev 0x5A][pad][03]
  H_B  普通参数打包: 一组 u32/u8 混合参数，其中的 0x5A 只是数值

可判定的硬证据：
  1. 若为 I2C 写序列，dev 地址必须是 **固定的**，reg 必须**变化**。
  2. 三段式若出现两次，且两次的 reg 相同(0x50) / cmd 相同(0x03)，则更像"重复的配置模板"
     而不是逐寄存器写序列。
  3. 真 I2C 序列里，len 字段必须等于后续 payload 长度。这里 len=04 但后面有 8 字节。
     若按 [len][dev][reg][len][data...] 解析 -> 04 5A 00 00 00 50 5A 00 00 00 00 03
     '04' 后面的 4 字节 = 5A 00 00 00；然后 '50 5A 00 00' —— 对不上。
  4. 检查同族配置（sid0/sid2/sid3）是否共享同一三段式 -> 共享则它是「芯片固定命令模板」
     而不是厂商自定义的 I2C 初始化。
"""
import os
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


# 三段式模式：从 5A 往后看
# 观测: 90 01 | 04 00 00 00 | 5A 00 00 00 50 00 5A 00 00 00 00 03
# 换个切法: 04 00 00 00 = u32 LE 4 ; 5A 00 00 00 = u32 LE 90 ; 50 00 = u16 80 ...
# 或: u32 LE 序列: 0x01 90 | 0x00000004 | 0x90000000 .. 说明按 u32 读不对

print("=" * 78)
print("三段式逐字节 u32/u16 双解读")
print("=" * 78)

for tag in ("sid0", "sid2", "sid3"):
    b = load(tag)
    print("\n### %s" % tag)
    for i in range(len(b) - 12):
        if b[i] == 0x5A and b[i + 4] == 0x50 and b[i + 6] == 0x5A:
            seg = b[i - 6:i + 12]
            print("  @0x%04X  ctx(前6/后12): %s" % (i, " ".join("%02X" % x for x in seg)))
            # u32 LE 解读
            u32 = [b[j] | b[j + 1] << 8 | b[j + 2] << 16 | b[j + 3] << 24 for j in range(i - 4, i + 8, 4)]
            print("        u32LE@%04X: %s" % (i - 4, [hex(v) for v in u32]))
            # u16 LE
            u16 = [b[j] | b[j + 1] << 8 for j in range(i - 4, i + 10, 2)]
            print("        u16LE@%04X: %s" % (i - 4, [hex(v) for v in u16]))

print("\n" + "=" * 78)
print("跨 sid 模板共享检验：搜索 '5A 00 00 00 50 00 5A' 模式")
print("=" * 78)
pat = bytes([0x5A, 0x00, 0x00, 0x00, 0x50, 0x00, 0x5A])
for tag in ("sid0", "sid2", "sid3"):
    b = bytes(load(tag))
    pos = []
    s = 0
    while True:
        k = b.find(pat, s)
        if k < 0:
            break
        pos.append(k)
        s = k + 1
    print("  %s: %d 处  %s" % (tag, len(pos), [hex(p) for p in pos]))

print("""
================================ 判读 ================================
若 '5A 00 00 00 50 00 5A' 在多个异构 cfg 中同时出现且前后对齐不同参数字段，
则它是「厂商写入芯片的固定命令模板」(Goodix 自己的 host 命令格式)，
   0x5A 在这里**不是** AW86927 的 I2C 从地址。

进一步：len=0x04 且其后跟 4 个字节 '5A 00 00 00'，
再跟 0x50 0x00 (u16=80) 再跟 '5A 00 00 00' 再跟 0x03
—— 更像一条「命令描述符」: [len=4][addr=0x5A][...][op=0x50][...][val/cmd=3]
   即 Goodix 内部 host 命令，用于让主机向芯片发控制命令。
""")
