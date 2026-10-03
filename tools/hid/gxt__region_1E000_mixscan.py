# -*- coding: utf-8 -*-
"""
0x1E000 = 代码 + 数据表 混合区：
 用"相对跳转偏移集中度"作为扫描判据（已在 0x00000真代码/0x1E000/随机 上验证有梯度）
 逐 512 B 窗口算 |rel|<=8 占比，找出代码段与数据段的分界。
"""
import os, collections, random, math

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "region_1E000_mixscan.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

SEG = data[0x1E000:0x20000]

RELOPS = (0x80,0x70,0x60,0x50,0x40,0x30,0x20,0x10,
          0x01,0x21,0x41,0x61,0x81,0xa1,0xc1,0xe1,
          0x11,0x31,0x51,0x71,0x91,0xb1,0xd1,0xf1)

def relscore(b):
    """|rel|<=8 的占比；样本量太小时返回 None"""
    n = 0; ok = 0
    for i in range(len(b)-1):
        if b[i] in RELOPS:
            rel = b[i+1]
            if rel >= 128: rel -= 256
            n += 1
            if abs(rel) <= 8: ok += 1
    if n < 8: return None, n
    return ok/n, n

w("=" * 80)
w("0x1E000 代码/数据分界扫描（判据 |rel|<=8 占比）")
w("=" * 80); w()

# 先建标尺
w("【标尺】")
w("  随机基线:        %.3f" % 0.077)
w("  真代码 0x00000:  %.3f" % relscore(data[0x00000:0x01000])[0])
w("  白化区 0x04000:  %.3f" % (relscore(data[0x04000:0x05000])[0] or 0))
w("  cfG   0x19000:  %.3f" % (relscore(data[0x19000:0x1A000])[0] or 0))
w()

w("【逐 512 B 扫描 0x1E000】")
w("  偏移      占比    样本量   判定")
rows = []
for o in range(0, len(SEG), 512):
    win = SEG[o:o+512]
    sc, n = relscore(win)
    if sc is None:
        w("  0x%05X   --      %3d    样本不足" % (0x1E000+o, n)); continue
    if sc >= 0.40:   v = "★ 代码"
    elif sc >= 0.20: v = "混合"
    else:            v = "数据"
    rows.append((0x1E000+o, sc, n, v))
    w("  0x%05X  %.3f   %3d    %s" % (0x1E000+o, sc, n, v))
w()

w("【汇总】")
codes = [r for r in rows if r[3] == "★ 代码"]
mixes = [r for r in rows if r[3] == "混合"]
dats = [r for r in rows if r[3] == "数据"]
w("  ★ 代码窗口 %d 个: %s" % (len(codes), [hex(r[0]) for r in codes]))
w("  混合窗口   %d 个" % len(mixes))
w("  数据窗口   %d 个" % len(dats))
w()

w("【对比：把 0x00000 明文头也逐 512 B 扫一遍】")
S0 = data[0x00000:0x01000]
for o in range(0, len(S0), 512):
    sc, n = relscore(S0[o:o+512])
    w("  0x%05X  %s  (n=%d)" % (0x00000+o, "%.3f" % sc if sc else "--", n))
w()

w("【对比：白化区 0x04000 逐 512 B】")
S4 = data[0x04000:0x05000]
for o in range(0, len(S4), 512):
    sc, n = relscore(S4[o:o+512])
    w("  0x%05X  %s  (n=%d)" % (0x04000+o, "%.3f" % sc if sc else "--", n))
w()

w("【补充】更稳健的判据：多指标合成标尺")
def composite(b):
    """返回 (指标字典)"""
    n = len(b)
    rel_n = 0; rel_ok = 0
    for i in range(n-1):
        if b[i] in RELOPS:
            rel = b[i+1] - 256 if b[i+1] >= 128 else b[i+1]
            rel_n += 1
            if abs(rel) <= 8: rel_ok += 1
    # 位操作指令（0x43/0x53 等 ORL direct,#imm）——真 C51 常见
    orl_n = b.count(0x43) + b.count(0x53)
    # 无条件跳转 0x80 SJMP
    sjmp = b.count(0x80)
    # MOV direct,# = 0x75
    mov75 = b.count(0x75)
    return {
        "rel": rel_ok/rel_n if rel_n else 0,
        "orl/KB": orl_n/(n/1024),
        "sjmp/KB": sjmp/(n/1024),
        "mov75/KB": mov75/(n/1024),
    }

w("  样本                    rel    orl/KB  sjmp/KB mov75/KB")
for nm, b in [("随机 8KB", os.urandom(8192)),
              ("真代码 0x00000 4K", data[0x00000:0x1000]),
              ("0x1E000 8K", SEG),
              ("0x19000 8K", data[0x19000:0x1A000]),
              ("白化 0x04000 8K", data[0x04000:0x06000])]:
    c = composite(b)
    w("  %-22s  %.3f   %6.1f  %6.1f  %6.1f" % (nm, c["rel"], c["orl/KB"], c["sjmp/KB"], c["mov75/KB"]))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
