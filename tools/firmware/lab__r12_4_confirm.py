# -*- coding: utf-8 -*-
"""R12-4 ★★★★★ 跨代「已知答案」验证：Goodix cfg 里存的到底是不是【坐标点数】= 输入 max + 1
 三份真实 Berlin/GT9916 cfg 包，各自代表一块已知面板：
   moto cybert      → 1220 x 2712
   moto dubai-csot  → 1080 x 2400
   xiaomi manet     → 1440 x 3200
 检验：① 该 (X,Y) 是否以【相邻 u16LE 对】出现在 cfg 数据里；
       ② 其【邻域模板】是否跨三块板一致（一致的常量 = 真结构，而不是巧合）；
       ③ 与本机（GT7868Q, u16BE, 4150/2148 = 描述符 4149/2147 + 1）是否同构。

★ 前置：先把 3 份真实 cfg 包放到 ./_r10/ 下（本仓库【不收录】这几份厂商二进制，红线），
  文件名须为 lfs-moto-cybert.dat / lfs-moto-dubai-csot.dat / lfs-xiaomi-manet.dat。
  出处（GitHub 仓库路径与取回方式）见 vendor-refs/links.md。
  本机样本 orig_TB14P.bin 需放在脚本同目录（= 本机 firmware container，见 docs/03-firmware 第四轮）。
"""
import os, collections

D = {}
for fn, res in [('lfs-moto-cybert.dat', (1220, 2712)),
                ('lfs-moto-dubai-csot.dat', (1080, 2400)),
                ('lfs-xiaomi-manet.dat', (1440, 3200))]:
    p = os.path.join('_r10', fn)
    if os.path.exists(p):
        D[fn] = (open(p, 'rb').read(), res)

print("=" * 98)
print("### 1 三块板的 (X,Y) 在 cfg 数据里出现几次、是否相邻成对")
print("=" * 98)
CS = 0x8B
loc = {}
for fn, (d, (x, y)) in D.items():
    pat = x.to_bytes(2, 'little') + y.to_bytes(2, 'little')
    pos = []
    st = CS
    while True:
        i = d.find(pat, st)
        if i < 0: break
        pos.append(i - CS); st = i + 1
    rev = y.to_bytes(2, 'little') + x.to_bytes(2, 'little')
    posr = []
    st = CS
    while True:
        i = d.find(rev, st)
        if i < 0: break
        posr.append(i - CS); st = i + 1
    loc[fn] = pos
    print(f"  {fn:<26} ({x},{y}) u16LE 正序 {len(pos)} 处 @ {[hex(p) for p in pos]}"
          f"   反序 {len(posr)} 处 @ {[hex(p) for p in posr]}")

print("\n" + "=" * 98)
print("### 2 ★★★ 邻域模板跨板对齐（用各自 (X,Y) 出现处为锚，取 +0 .. +0x40）")
print("=" * 98)
for fn, (d, (x, y)) in D.items():
    if not loc[fn]: continue
    a = loc[fn][0] + CS
    print(f"\n  --- {fn}  ({x}x{y}) ---")
    for r in range(0, 0x40, 16):
        bb = d[a+r:a+r+16]
        v = ' '.join('%02x' % t for t in bb)
        u = ' '.join('%5d' % int.from_bytes(bb[i:i+2], 'little') for i in (0, 2, 4, 6))
        print(f"    +{r:02X}  {v}   LE:[{u}]")

print("\n" + "=" * 98)
print("### 3 板间公共常量（若邻域里有跨板不变的 u16，即是真参数模板）")
print("=" * 98)
seq = {}
for fn, (d, (x, y)) in D.items():
    if not loc[fn]: continue
    a = loc[fn][0] + CS
    seq[fn] = [int.from_bytes(d[a+i:a+i+2], 'little') for i in range(0, 0x40, 2)]
ks = list(seq)
for i in range(len(seq[ks[0]])):
    vals = [seq[k][i] for k in ks]
    if len(set(vals)) == 1:
        print(f"  +{i*2:02X}  三块板全等 = {vals[0]}")

print("\n" + "=" * 98)
print("### 4 与【本机】并排：本机是 u16BE，值是描述符 max+1")
print("=" * 98)
tb = open('orig_TB14P.bin', 'rb').read()
base = 0x4C
for r in range(0x100, 0x130, 16):
    bb = tb[base+r:base+r+16]
    be = ' '.join('%5d' % int.from_bytes(bb[i:i+2], 'big') for i in (0, 2, 4, 6))
    print(f"    +{r:03X}  {' '.join('%02x' % t for t in bb)}   BE:[{be}]")
print("  本机 cfg +0x10F/+0x111 u16BE = 4150 / 2148   描述符真值 4149 / 2147  ⇒ +1")
