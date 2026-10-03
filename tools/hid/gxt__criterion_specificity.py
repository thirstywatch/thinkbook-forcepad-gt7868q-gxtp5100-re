# -*- coding: utf-8 -*-
# 第十九轮 E：为什么 |rel|<=8 判据在 0x1E000 上给出 0.328（误导）
# 该判据假设"字节流是 8051 代码"。但 0x1E000 是 ARM Thumb。
# 需要检查：在 ARM Thumb 代码上跑 8051 相对跳转判据，会得到什么值？
# 若 ARM 代码也能给出 0.3 级别，则该判据"不专一"，不能用来断定 8051。
import struct, os
from collections import Counter

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

w("="*78)
w("判据专一性检验：8051 相对跳转判据跑在 ARM Thumb 代码上（第十九轮 E）")
w("="*78)

# 8051 相对跳转操作码
SJMP = 0x80
JREL = {0x70,0x60,0x50,0x40,0x38,0x30,0x28,0x20,0x78,0x68,0x58,0x48,0x18,0x10,0x08,0xD8,0xC8,0xB8,0xA8,0x98,0x88}

def relstat(buf):
    """返回 |rel|<=8 占比 与 样本数"""
    n = len(buf)
    vals = []
    for i in range(n - 1):
        op = buf[i]
        if op == SJMP or op in JREL:
            rel = buf[i+1]
            if rel >= 128: rel -= 256
            vals.append(rel)
    if not vals:
        return None, 0, []
    hit = sum(1 for v in vals if abs(v) <= 8) / len(vals)
    return hit, len(vals), vals

# 关键样本
samples = [
    ('随机 os.urandom 4K',   os.urandom(4096)),
    ('白化区 0x04000 4K',     D[0x04000:0x04000+4096]),
    ('官方CFG 0x19000 2K',   D[0x19000:0x19000+2048]),
    ('0x1E000 全8K (实际ARM)', D[0x1E000:0x1E000+8192]),
    ('尾部 ARM 0x1A000 4K',  D[0x1A000:0x1A000+4096]),
    ('尾部 ARM 0x22000 4K',  D[0x22000:0x22000+4096]),
    ('尾部 ARM 0x24000 4K',  D[0x24000:0x24000+4096]),
    ('8051 真代码 0x00000 4K', D[0x00000:0x00000+4096]),
    ('8051 真代码 0x00100 1K', D[0x00100:0x00100+1024]),
]
w()
w("### 1. |rel|<=8 判据在各类样本上的读数")
w("    样本                         |rel|<=8   样本数   中位|rel|")
for nm, buf in samples:
    h, n, vals = relstat(buf)
    if h is None:
        w("    %-26s  (无匹配)" % nm); continue
    vals_s = sorted(abs(v) for v in vals)
    med = vals_s[len(vals_s)//2]
    w("    %-26s  %.3f     %-6d   %d" % (nm, h, n, med))

w()
w("### 2. ★结论：该判据对 ARM Thumb 代码也给出高读数 → 不专一")
w("    若 ARM 代码读数与 8051 代码同量级，则该判据只能区分【代码 vs 非代码】，")
w("    不能区分【8051 vs ARM】。上一轮据此断'0x1E000 有 8051 代码段'的结论作废。")

# ---------- 3. 反过来：用 Thumb-2 判据去测 0x00000（8051真代码）----------
w()
w("### 3. 反向对照：Thumb-2 0xF2xx 富集度")
def f2(buf):
    tot=0; hit=0
    for i in range(0, len(buf)-1, 2):
        hw = buf[i] | (buf[i+1]<<8)
        tot += 1
        if 0xF200 <= hw <= 0xF2FF: hit += 1
    return hit/tot if tot else 0, hit, tot
for nm, buf in samples:
    r,h,t = f2(buf)
    w("    %-26s  %.5f  (x%.1f)" % (nm, r, r/0.00390625))

# ---------- 4. 交叉表：两种判据的联合判别力 ----------
w()
w("### 4. 联合判别表（rel 读数 × Thumb2 读数）")
w("    样本                       rel<=8    F2xx富集   -> 判定")
rows = []
for nm, buf in samples:
    h, n, vals = relstat(buf)
    r, hh, t = f2(buf)
    if h is None: h = -1
    if r > 0.04:
        verd = '★ARM Thumb-2 代码'
    elif h > 0.30:
        verd = '代码(非ARM)'
    else:
        verd = '数据/白化'
    rows.append((nm, h, r/0.00390625, verd))
for nm, h, e, verd in rows:
    w("    %-26s  %.3f    x%-6.1f  %s" % (nm, h, e, verd))

# ---------- 5. 0x1E000 的窗口扫描，改用 Thumb-2 判据 ----------
w()
w("### 5. 0x1E000 的 512B 窗口扫描（改用 Thumb-2 0xF2xx 富集判据）")
w("    窗口        熵      F2xx占比   富集   旧rel读数  新判定")
base = 0x1E000
for off in range(0x1E000, 0x20000, 512):
    buf = D[off:off+512]
    # 熵
    c = Counter(buf)
    ent = -sum((v/len(buf))*__import__('math').log2(v/len(buf)) for v in c.values())
    r, hh, t = f2(buf)
    h, n, vals = relstat(buf)
    if r > 0.045:
        verd = 'ARM代码'
    elif r < 0.015:
        verd = '数据'
    else:
        verd = '混合'
    w("    0x%05X  %.3f   %.5f   x%-5.1f  %.3f     %s" % (off, ent, r, r/0.00390625, h if h is not None else -1, verd))

# ---------- 6. 对 0x1E000 做真正的 Thumb-2 反汇编抽样（前 64 B）----------
w()
w("### 6. 0x1E000 开头 128 B 的 Thumb-2 逐指令解码抽样")
# 用简化解码：只标出宽度与几个已知前缀
i = 0x1E000
cnt = 0
while i < 0x1E000 + 128 and cnt < 40:
    hw = D[i] | (D[i+1] << 8)
    top5 = hw >> 11
    if top5 in (0b11101, 0b11110, 0b11111):
        hw2 = D[i+2] | (D[i+3] << 8)
        w("    0x%05X  %s %s   [32-bit]" % (i,
          ' '.join('%02x'%b for b in D[i:i+2]),
          ' '.join('%02x'%b for b in D[i+2:i+4])))
        i += 4
    else:
        w("    0x%05X  %s            [16-bit]" % (i, ' '.join('%02x'%b for b in D[i:i+2])))
        i += 2
    cnt += 1

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed', 'criterion_specificity.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
