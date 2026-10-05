# -*- coding: utf-8 -*-
"""R8-3 ★★★ 决定性第二台机器验证：在 cfg 文件里搜「(X LogicalMax+1, Y LogicalMax+1)」相邻对
 已知描述符（工区 wiki，第二/第三台机器）：
   Goodix GT7863 : X 3455  Y 2159  -> 预测 cfg 里相邻出现 (3456=0x0D80, 2160=0x0870)
   ELAN          : X 3679  Y 2261  -> 预测 (3680=0x0E60, 2262=0x08D6)
 本机（GT7868Q，实测）: X 4149  Y 2147 -> 已知命中 (4150,2148) @ cfg +0x10F/+0x111
 待验 cfg：sid0(小米7867) / sid2(7863) / sid3(LaiBao 7986P) / sid0/2/3 的 cfg.txt 十六进制导出
"""
import os, re, glob

CFGDIR = r"<WORKSPACE>"
REPO_REF = r"<WORKSPACE>"

PAIRS = {
    'Goodix GT7863 (X3455,Y2159)': (3456, 2160),
    'ELAN (X3679,Y2261)': (3680, 2262),
    '本机 GT7868Q (X4149,Y2147)': (4150, 2148),
    'capsule 机型 (X3243,Y2015)?': (3244, 2016),
}

SRC = {}
for p in sorted(glob.glob(os.path.join(CFGDIR, "*.bin"))):
    SRC[os.path.basename(p)] = open(p, 'rb').read()
for p in sorted(glob.glob(os.path.join(REPO_REF, "*.cfg.txt"))):
    txt = open(p, encoding="utf-8", errors="replace").read()
    bs = bytes(int(x, 16) for x in re.findall(r"0[xX]([0-9A-Fa-f]{2})", txt))
    SRC["cfg.txt:" + os.path.basename(p)] = bs
# 本机容器配置体作对照
SRC["本机容器"] = open(r"<WORKSPACE>", 'rb').read()

print("=" * 100)
print("### 在所有候选 cfg 里搜「两个值相邻（相距 2 字节）」以及各自的单独命中")
print("=" * 100)
for nm, d in SRC.items():
    print(f"\n--- {nm} ({len(d)} B) ---")
    for tag, (x, y) in PAIRS.items():
        for endian in ('big', 'little'):
            xb = x.to_bytes(2, endian); yb = y.to_bytes(2, endian)
            adj = [i for i in range(len(d) - 4) if d[i:i+2] == xb and d[i+2:i+4] == yb]
            rev = [i for i in range(len(d) - 4) if d[i:i+2] == yb and d[i+2:i+4] == xb]
            if adj or rev:
                print(f"    ★★★ {tag}  {endian}: 相邻命中 adj@{[hex(i) for i in adj]}  rev@{[hex(i) for i in rev]}")
        # 单独命中数（用于判断是否有意义）
        cx = sum(1 for i in range(len(d)-1) if d[i:i+2] in (x.to_bytes(2,'big'), x.to_bytes(2,'little')))
        cy = sum(1 for i in range(len(d)-1) if d[i:i+2] in (y.to_bytes(2,'big'), y.to_bytes(2,'little')))
        print(f"        {tag:<30} 单独命中 X={cx}  Y={cy}")

print("\n" + "=" * 100)
print("### ★ 反向思路：看每个 cfg 里最常见的相邻 u16 对（BE）")
print("=" * 100)
import collections
for nm, d in SRC.items():
    c = collections.Counter()
    for i in range(0, len(d) - 3):
        c[(int.from_bytes(d[i:i+2], 'big'), int.from_bytes(d[i+2:i+4], 'big'))] += 1
    top = [(f"{a}/{b}", n) for (a, b), n in c.most_common(6)]
    print(f"  {nm:<34} 常见相邻对(BE) {top}")
