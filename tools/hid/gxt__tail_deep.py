# -*- coding: utf-8 -*-
"""
★★★ 固件明文尾区（0x19A00-0x2775C, ~56 KB）完整挖掘
 1. 精确的明文/白化分界
 2. 关键字符串及其上下文（TF100A_Test_FW / 版本 / 编译时间）
 3. 0x26551 处的"规律重复"结构（查表？）
 4. 0x19A00 区（rel 1.000）到底是什么
 5. 这一区与已知的 TF100A 关系
"""
import os, collections, math

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "tail_deep.txt")
data = open(FW, "rb").read()
L = len(data)
lines = []
def w(s=""):
    lines.append(s); print(s)

def H(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum(v/n*math.log2(v/n) for v in c.values())

w("=" * 84)
w("固件明文尾区完整挖掘")
w("=" * 84); w()

w("【1】TF100A_Test_FW 字符串及其上下文（0x19E80 - 0x19F60）")
for o in range(0x19E80, 0x19F60, 16):
    raw = data[o:o+16]
    asc = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in raw)
    w("  0x%05X  %-47s  %s" % (o, raw.hex(" "), asc))
w()

w("【2】版本号区上下文（0x26180 - 0x26240）")
for o in range(0x26180, 0x26240, 16):
    raw = data[o:o+16]
    asc = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in raw)
    w("  0x%05X  %-47s  %s" % (o, raw.hex(" "), asc))
w()

w("【3】5.21.01.23007 上下文（0x264A0 - 0x26540）")
for o in range(0x264A0, 0x26540, 16):
    raw = data[o:o+16]
    asc = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in raw)
    w("  0x%05X  %-47s  %s" % (o, raw.hex(" "), asc))
w()

w("【4】0x26551 的规律重复结构（0x26540 - 0x266C0）")
for o in range(0x26540, 0x266C0, 16):
    raw = data[o:o+16]
    asc = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in raw)
    w("  0x%05X  %-47s  %s" % (o, raw.hex(" "), asc))
w()

w("【5】0x19A00 - 0x19A80（rel 达 1.000 的窗口）")
for o in range(0x199C0, 0x19A90, 16):
    raw = data[o:o+16]
    asc = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in raw)
    w("  0x%05X  %-47s  %s" % (o, raw.hex(" "), asc))
w()

w("【6】0x19A00 窗口是 16 位模式吗？（u16 与小端/大端）")
seg = data[0x19A00:0x19A80]
w("  熵 %.3f  零占比 %.3f" % (H(seg), seg.count(0)/len(seg)))
w("  u16LE: %s" % " ".join("%04X" % int.from_bytes(seg[i:i+2], "little") for i in range(0, 64, 2)))
w("  u16BE: %s" % " ".join("%04X" % int.from_bytes(seg[i:i+2], "big") for i in range(0, 64, 2)))
# 看是否为"每 2 字节重复相同值"
rep = sum(1 for i in range(0, 62, 2) if seg[i] == seg[i+1])
w("  相邻两字节相同的位置数: %d / 32" % rep)
w()

w("【7】明文尾区的整体 ASCII 密度（逐 512 B）")
w("  偏移      可打印%  熵")
for o in range(0x19A00, L-512+1, 512):
    win = data[o:o+512]
    pr = sum(1 for b in win if 0x20 <= b < 0x7f)/512
    w("  0x%05X   %5.1f   %.3f" % (o, pr*100, H(win)))
w()

w("【8】整个固件的可打印 ASCII 密度地图（逐 1024 B，只列 > 12% 的）")
w("  偏移      可打印%  熵      判定")
for o in range(0, L-1024+1, 1024):
    win = data[o:o+1024]
    pr = sum(1 for b in win if 0x20 <= b < 0x7f)/1024
    if pr > 0.12:
        w("  0x%05X   %5.1f   %.3f   %s" % (o, pr*100, H(win),
          "★ 文本密集" if pr > 0.25 else "有文本"))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
