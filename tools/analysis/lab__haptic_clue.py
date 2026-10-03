"""在 GT7868Q 明文固件里搜触觉（AW86927 / LRA）线索。

目标：
 T1 是否直接引用 AW86927 的 I²C 地址（0x5A/0x5B，8 位形态 0xB4-B7）
 T2 是否引用 AW86927 的寄存器地址（0x00-0xFF 小偏移）
 T3 是否引用 I²C 外设（找 I²C 控制器的基址常量）
 T4 触觉相关常量（波形时长 / 强度 / 时间参数）
 T5 与 TF100A 对照（TF100A 是明文，已知它不驱动 AW86927）
"""
import os
import collections
import re

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
SEG_S, SEG_E = 0x1200, 0x19800
seg = d[SEG_S:SEG_E]

print("=" * 90)
print("① Thumb「MOVS rX, #imm8」模式（编码 xx 20..27）—— 找 I²C 地址立即数")
print("=" * 90)
targets = [
    (0x5A, "AW86927 7 位地址 候选 A"),
    (0x5B, "AW86927 7 位地址 候选 B"),
    (0xB4, "0x5A<<1 写地址"),
    (0xB5, "0x5A<<1|1 读地址"),
    (0xB6, "0x5B<<1 写地址"),
    (0xB7, "0x5B<<1|1 读地址"),
    (0xCA, "CA4F 高字节"),
    (0x4F, "CA4F 低字节"),
    (0x2C, "触控板自身 I²C 地址 (TPAD 0x2C)"),
    (0x58, "TF100A OAR1 = 0x58"),
]
for val, desc in targets:
    hits = [i for i in range(len(d) - 1) if d[i] == val and 0x20 <= d[i + 1] <= 0x27]
    in_seg = [h for h in hits if SEG_S <= h < SEG_E]
    print("  MOVS rX,#%#04x  %-34s 全文件 %3d 处 (加扰区 %3d)  %s" % (
        val, desc, len(hits), len(in_seg),
        " ".join("0x%05X" % h for h in hits[:8])))
print()

print("=" * 90)
print("② 32 位小端常量（字面量池 / 比较对象）")
print("=" * 90)
for v, desc in [(0x5A, ""), (0x5B, ""), (0xB4, ""), (0xB6, ""),
                (0xCA4F, "CA4F"), (0x5A5B, ""), (0x0000002C, "")]:
    p = v.to_bytes(4, "little")
    c = d.count(p)
    pos = [m.start() for m in re.finditer(re.escape(p), d)]
    print("  %#010x %-8s 出现 %2d 次  %s" % (v, desc, c,
          " ".join("0x%05X" % x for x in pos[:8])))
print()

print("=" * 90)
print("③ 单字节频率（快筛：哪些值异常稀少/异常多）")
print("=" * 90)
cnt = collections.Counter(seg)
n = len(seg)
exp = n / 256
for val in (0x5A, 0x5B, 0xB4, 0xB5, 0xB6, 0xB7, 0xCA, 0x4F, 0x2C, 0x58, 0x00, 0xFF):
    c = cnt.get(val, 0)
    print("  %#04x  出现 %5d 次  期望 %.1f  比值 %.2f×" % (val, c, exp, c / exp))
print()

print("=" * 90)
print("④ 常见 Cortex-M 外设基址常量（判断是否 ARM 及外设布局）")
print("=" * 90)
for v, desc in [(0x40000000, "外设区基址"), (0x40010000, "APB1"),
                (0x40005400, "I²C1 (STM32)"), (0x40003000, "I²C1 (LPC/其他)"),
                (0x40020000, "AHB1"), (0x40021000, "RCC"),
                (0xE000E000, "SCB/NVIC"), (0x20000000, "SRAM"),
                (0x08000000, "Flash"), (0x00000000, "别名")]:
    p = v.to_bytes(4, "little")
    c = d.count(p)
    pos = [m.start() for m in re.finditer(re.escape(p), d)]
    print("  %#010x %-16s 出现 %2d 次  %s" % (v, desc, c,
          " ".join("0x%05X" % x for x in pos[:6])))
print()

print("=" * 90)
print("⑤ 16 位小端「外设地址高半字」扫描（Thumb 常用 MOVW/MOVT）")
print("=" * 90)
hcnt = collections.Counter(seg[i] | (seg[i + 1] << 8) for i in range(0, len(seg) - 1, 2))
print("  出现次数最多的 16 位值（Top 20）:")
for v, c in hcnt.most_common(20):
    print("    0x%04X  %5d 次" % (v, c))
print()

print("=" * 90)
print("⑥ 明文头（0x0000-0x1200）里的 32 位常量池")
print("=" * 90)
head = d[:0x1200]
hc = collections.Counter(head[i:i + 4] for i in range(0, len(head) - 3, 2))
print("  头部 4 字节窗口 Top 15:")
for w, c in hc.most_common(15):
    print("    %s  ×%d" % (w.hex(), c))
