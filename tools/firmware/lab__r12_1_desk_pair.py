# -*- coding: utf-8 -*-
"""R12-1 ★★★★★ 能不能在【同一份样本内】凑齐 (描述符, cfg) 配对？
 四份含 cfg 的样本：
   orig_TB14P.bin   161628   —— 待确认是不是本机
   cap22001E0D.Cap  133716   —— GT7868Q（YELSTO/7868Q, fw_flag 0x0C, 2.0.30）机型B
   cap26002816.Cap  140796   —— GT7868Q, 2.0.40 机型B（同机型新版本）
   (本机容器)
 已定标：cfg body +0x10F u16BE = X点数, +0x111 = Y点数
  本机 4150/2148（描述符 4149/2147）
  capA/B 3244/2016 ⇒ 预测描述符 3243/2015
 ★ 本轮要查：capA/capB 里是否【内嵌了它自己面板的 HID 描述符】——
   若内嵌，则我们第一次拿到"同一台机器的 (描述符, cfg) 完整配对"，`+1` 规则即可就地定案。
"""
import os, re, struct

FILES = {
 'orig_TB14P':   'orig_TB14P.bin',
 'cap22001E0D':  'cap22001E0D.Cap',
 'cap26002816':  'cap26002816.Cap',
}
D = {}
for k, p in FILES.items():
    if os.path.exists(p):
        D[k] = open(p, 'rb').read()

print("样本:", {k: len(v) for k, v in D.items()})

def copies(d, val, stride=1084, n=4):
    """在 d 里把所有 u16BE == val 的位置找出来，看是否能凑成长 stride 的 4 连"""
    t = val.to_bytes(2, 'big')
    pos = [i for i in range(len(d) - 1) if d[i:i+2] == t]
    return pos

print("\n" + "=" * 96)
print("### 1 每份样本：定位 cfg 4 副本（用已知的 X 点数作锚）")
print("=" * 96)
for k, d in D.items():
    print(f"\n--- {k} ({len(d)} B) ---")
    for name, val in [('X点数(本机) 4150', 4150), ('Y点数(本机) 2148', 2148),
                      ('X点数(机型B) 3244', 3244), ('Y点数(机型B) 2016', 2016)]:
        p = copies(d, val)
        if p:
            print(f"  {name}: {len(p)} 处 @ {[hex(x) for x in p[:8]]}")
            if len(p) >= 2:
                diffs = [p[i+1] - p[i] for i in range(len(p) - 1)]
                print(f"      间距: {diffs}")

print("\n" + "=" * 96)
print("### 2 ★★★ 全文件搜「描述符骨架」——它是否内嵌了自己的 HID 描述符？")
print("=" * 96)
PATS = {
 '触摸板集合 05 0D 09 05 A1 01': bytes.fromhex('050D0905A101'),
 'Digitizer 05 0D 09 05': bytes.fromhex('050D0905'),
 'Finger 09 22': bytes.fromhex('0922'),
 'TipSwitch 09 42': bytes.fromhex('0942'),
 'X 用法 09 30': bytes.fromhex('0930'),
 'Y 用法 09 31': bytes.fromhex('0931'),
 '压力 09 30(0x0D页)': bytes.fromhex('050D'),
 'LogicalMax 3243 26 AB 0C': bytes.fromhex('26AB0C'),
 'LogicalMax 2015 26 DF 07': bytes.fromhex('26DF07'),
 'LogicalMax 3244 26 AC 0C': bytes.fromhex('26AC0C'),
 'LogicalMax 2016 26 E0 07': bytes.fromhex('26E007'),
 'LogicalMax 4149 26 35 10': bytes.fromhex('263510'),
 'LogicalMax 2147 26 63 08': bytes.fromhex('266308'),
 'LogicalMax 3684 26 64 0E': bytes.fromhex('26640E'),
 'LogicalMax 2176 26 80 08': bytes.fromhex('268008'),
}
for k, d in D.items():
    print(f"\n--- {k} ---")
    for name, pat in PATS.items():
        c = d.count(pat)
        if c:
            pos = [m.start() for m in re.finditer(re.escape(pat), d)][:5]
            print(f"  {name:<34} {c} 处 @ {[hex(x) for x in pos]}")

print("\n" + "=" * 96)
print("### 3 ★★★ 相邻对搜索：26 <lo> <hi> 26 <lo> <hi>（描述符里 X/Y 通常紧邻）")
print("=" * 96)
CAND = [(4149, 2147, '本机'), (3243, 2015, 'capB预测'), (3684, 2176, 'GXTP7863(01E0)'),
        (3455, 2159, 'wiki GT7863'), (3679, 2261, 'ELAN')]
for k, d in D.items():
    print(f"\n--- {k} ---")
    hit = False
    for x, y, tag in CAND:
        for xo, yo in ((x, y), (y, x)):
            pat = bytes([0x26, xo & 0xFF, xo >> 8, 0x26, yo & 0xFF, yo >> 8])
            if pat in d:
                pos = [m.start() for m in re.finditer(re.escape(pat), d)]
                print(f"  ★★★ [{tag}] 26 {xo:04X} 26 {yo:04X}  @ {[hex(p) for p in pos]}"); hit = True
    if not hit:
        print("  （无）")

print("\n" + "=" * 96)
print("### 4 也搜 '26 xx xx' 单条 + 附近是否有 05 0D 09 05")
print("=" * 96)
for k, d in D.items():
    seqs = []
    for m in re.finditer(rb'\x26(..)', d):
        v = m.group(1)[0] | (m.group(1)[1] << 8)
        if 1000 <= v <= 5000:
            seqs.append((m.start(), v))
    if seqs:
        print(f"  {k}: 26 xx xx (1000..5000) 共 {len(seqs)} 处 → {[(hex(p), v) for p, v in seqs[:14]]}")
