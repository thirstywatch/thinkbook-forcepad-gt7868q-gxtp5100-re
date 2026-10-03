# -*- coding: utf-8 -*-
# 第十九轮 D ★决定性验证★
# 假设：0x1E000 的 c2 f2 是 ARM Thumb-2 的 MOVW/MOVT 宽指令前缀 0xF2C2
#   Thumb-2: MOVW Rd,#imm16 = 11110 i 10 0100 imm4 | 0 Rd imm3 imm8
#            第一半字 = 0xF24x ~ 0xF2Cx 之间（i=0/1, imm4 变化）
#   MOVT Rd,#imm16 = 11110 i 10 1100 imm4 | ...
#   即 0xF2C0-0xF2CF 就是 MOVT 系列！
# 验证方法：把 0x1E000 当 Thumb 反汇编，看指令边界是否自洽（覆盖率高 & 长度合理）
#   —— 但这是"退化判据"风险。改用"受控梯度测试"：
#   同一解码器分别跑 随机/白化/明文真代码/0x1E000，看能否分出梯度
import struct, os, random
from collections import Counter

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

w("="*78)
w("★决定性验证：0x1E000 是不是 ARM Thumb-2 代码（第十九轮 D）")
w("="*78)

# ---------- 0. Thumb-2 宽指令前缀理论 ----------
w()
w("### 0. Thumb-2 第一半字编码规则")
w("  Thumb-2 32位指令第一半字高5位 = 11101 / 11110 / 11111")
w("  即 0xE800-0xEFFF / 0xF000-0xF7FF / 0xF800-0xFFFF")
for lo, hi, nm in [(0xE800,0xF000,'E8xx-F0xx'),(0xF000,0xF800,'F0xx-F7xx'),(0xF800,0x10000,'F8xx-FFxx')]:
    n = 0
    for i in range(0x1E000, 0x20000, 2):
        hw = D[i] | (D[i+1] << 8)
        if lo <= hw < hi: n += 1
    w("    0x1E000 内落在 %s 的半字: %d" % (nm, n))
w()
w("  0xF2C0-0xF2CF 具体计数（MOVT 家族）：")
c = Counter()
for i in range(0x1E000, 0x20000, 2):
    hw = D[i] | (D[i+1] << 8)
    if 0xF2C0 <= hw <= 0xF2CF:
        c[hw] += 1
for hw, n in sorted(c.items()):
    w("    0x%04X  x%d" % (hw, n))
w("  合计 %d" % sum(c.values()))
w()
w("  0xF240-0xF24F（MOVW 家族）计数：")
c2 = Counter()
for i in range(0x1E000, 0x20000, 2):
    hw = D[i] | (D[i+1] << 8)
    if 0xF240 <= hw <= 0xF24F:
        c2[hw] += 1
for hw, n in sorted(c2.items()):
    w("    0x%04X  x%d" % (hw, n))
w("  合计 %d" % sum(c2.values()))

# ---------- 1. ★受控梯度测试：Thumb-2 前缀密度 ----------
w()
w("### 1. ★受控梯度测试：Thumb-2 宽指令前缀(0xE8-0xEF/0xF0-0xF7/0xF8-0xFF 高5位)在半字流中的占比")
w("    (真 ARM 代码应显著高于随机基线)")
def thumb32_rate(buf, base):
    n = len(buf) - 1
    n32 = 0
    tot = 0
    i = 0
    while i < n:
        hw = buf[i] | (buf[i+1] << 8)
        tot += 1
        top5 = hw >> 11
        if top5 in (0b11101, 0b11110, 0b11111):
            n32 += 1
            i += 4   # 跳过 32 位指令
        else:
            i += 2
    return n32 / tot if tot else 0, n32, tot

samples = [
    ('随机 os.urandom 4K',      os.urandom(4096), 0),
    ('白化区 0x04000',           D[0x04000:0x04000+4096], 0x04000),
    ('官方CFG 0x19000',         D[0x19000:0x19000+2048], 0x19000),
    ('0x1E000 前4K',            D[0x1E000:0x1E000+4096], 0x1E000),
    ('0x1E000 后4K',            D[0x1C000:0x1C000+4096], 0x1C000),
    ('0x1E000 全 8K',           D[0x1E000:0x1E000+8192], 0x1E000),
    ('★尾部 ARM 0x1A000 4K',    D[0x1A000:0x1A000+4096], 0x1A000),
    ('★尾部 ARM 0x22000 4K',    D[0x22000:0x22000+4096], 0x22000),
    ('★尾部 ARM 0x26000 4K',    D[0x26000:0x26000+4096], 0x26000),
    ('8051 真代码 0x00000',     D[0x00000:0x00000+4096], 0),
]
w("    样本                        32位指令占比   32位指令数/总指令数")
for nm, buf, _ in samples:
    r, n32, tot = thumb32_rate(buf, 0)
    w("    %-26s  %.4f        %d/%d" % (nm, r, n32, tot))

# ---------- 2. 用 0xF2xx 作为"ARM Thumb-2 指纹"做同样的梯度 ----------
w()
w("### 2. 指纹密度：u16LE 落在 0xF200-0xF2FF 的半字占比（受控梯度）")
w("    (Thumb-2 MOVW/MOVT/MOV 宽指令前缀带；真 ARM 代码应显著富集)")
def f2rate(buf):
    n = len(buf) - 1
    tot = 0; hit = 0
    for i in range(0, n, 2):
        hw = buf[i] | (buf[i+1] << 8)
        tot += 1
        if 0xF200 <= hw <= 0xF2FF:
            hit += 1
    return hit / tot if tot else 0, hit, tot

w("    样本                        0xF2xx 占比   (随机期望 0.0039)")
for nm, buf, _ in samples:
    r, h, t = f2rate(buf)
    w("    %-26s  %.5f   x%.1f 富集   (%d/%d)" % (nm, r, r/0.00390625, h, t))

# ---------- 3. 指令边界自洽性：连续两条 32 位指令 ----------
w()
w("### 3. 指令流自洽性：找到 0xF2C2 后，其前一条指令是否也能自洽解码")
w("    做法：从 0x1E000 顺序解码，遇宽指令跳4，记录落点处的半字分布")
w("    若解码正确，落点应均匀覆盖全部半字；若错误，会系统性地撞在特定值上")
def decode_walk(buf, start=0):
    i = start
    n = len(buf) - 3
    lands = Counter()
    steps = Counter()
    while i < n:
        hw = buf[i] | (buf[i+1] << 8)
        top5 = hw >> 11
        if top5 in (0b11101, 0b11110, 0b11111):
            i += 4; steps[4] += 1
        else:
            i += 2; steps[2] += 1
        lands[hw] += 1
    return steps, lands

for nm, buf in [('0x1E000 全8K', D[0x1E000:0x1E000+8192]),
                ('0x00000 8051真代码4K(对照)', D[0x00000:0x00000+4096]),
                ('随机4K', os.urandom(4096))]:
    steps, lands = decode_walk(buf)
    tot = sum(steps.values())
    w("    %-28s 2字节步 %d  4字节步 %d  (4字节占比 %.3f)  总条数 %d"
      % (nm, steps[2], steps[4], steps[4]/tot if tot else 0, tot))

# ---------- 4. 0x1E000 里 c2 f2 序列的前半字（即完整的 4 字节） ----------
w()
w("### 4. 0x1E000 中 c2 f2 完整指令模式统计（前2字节 + c2 f2 + 后2字节）")
pat = b'\xc2\xf2'
locs = []
s = 0
while True:
    i = D.find(pat, s, 0x20000)
    if i < 0: break
    locs.append(i); s = i + 1
w("  在 0x1E000-0x20000 内 c2 f2 出现 %d 次" % len(locs))
if locs:
    w("  其位置 mod 4 分布: %s" % dict(Counter(l % 4 for l in locs)))
    w("  其位置 mod 2 分布: %s" % dict(Counter(l % 2 for l in locs)))
    pre = Counter()
    for l in locs:
        if l >= 2: pre[D[l-2] | (D[l-1] << 8)] += 1
    w("  前 2 字节 top10: %s" % str(pre.most_common(10)))
    post = Counter()
    for l in locs:
        if l + 4 <= 0x20000: post[D[l+2] | (D[l+3] << 8)] += 1
    w("  后 2 字节 top10: %s" % str(post.most_common(10)))

# ---------- 5. 对照：c2 f2 在真 8051 代码 0x00000 里的出现 ----------
w()
w("### 5. 对照：c2 f2 在 8051 真代码 0x00000-0x1000 里出现次数")
n0 = D[0:0x1000].count(b'\xc2\xf2')
w("    0x00000-0x01000 (8051 真代码): %d 次" % n0)
n1 = D[0x04000:0x20000].count(b'\xc2\xf2')
w("    0x04000-0x20000 (白化+CFG+1E000): %d 次" % n1)
n2 = D[0x1A000:].count(b'\xc2\xf2')
w("    0x1A000-END (ARM Thumb 尾区): %d 次" % n2)

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed', 'thumb2_verdict.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
