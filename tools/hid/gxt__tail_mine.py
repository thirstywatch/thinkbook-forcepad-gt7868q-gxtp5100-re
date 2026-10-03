# -*- coding: utf-8 -*-
# 第十九轮：开采固件尾部 55KB 明文（0x19A00-END）——不搜触觉词，改看它到底写了什么
# 目标：
#  A. 完整摊开 TF100A_Test_FW 构建信息块 0x19E80-0x19F80
#  B. 版本块 0x26180-0x26240 / 0x264A0-0x26540
#  C. 全部 ASCII 串按"是否可读"分级列出（>=8字符，且可打印占比>=0.9 才算真串）
#  D. ARM Thumb 函数边界定位（PUSH {...,LR} / BX LR 配对）
#  E. printf 调用面：找 BL 到 0x26xxx 区（C 库）的调用点
#  F. u16/u32 常量表识别
import struct, os, re, math
from collections import Counter, defaultdict

P = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
D = open(P, 'rb').read()
OUT = []
def w(s=''):
    OUT.append(s)

w("="*78)
w("固件尾部明文开采（第十九轮）  文件 %d B = 0x%X" % (len(D), len(D)))
w("="*78)

def hx(off, n):
    return ' '.join('%02x' % b for b in D[off:off+n])

def ascii_run(off, n):
    return ''.join(chr(b) if 32 <= b < 127 else '.' for b in D[off:off+n])

# ---------- A. 构建信息块 ----------
w()
w("### A. TF100A_Test_FW 构建信息块 0x19E80-0x19F80")
for off in range(0x19E80, 0x19F80, 16):
    w("  0x%05X  %-47s  %s" % (off, hx(off, 16), ascii_run(off, 16)))

# ---------- B. 版本块 ----------
w()
w("### B. 版本块 0x26180-0x26260")
for off in range(0x26180, 0x26260, 16):
    w("  0x%05X  %-47s  %s" % (off, hx(off, 16), ascii_run(off, 16)))
w()
w("### B2. 5.21.01.23007 附近 0x264A0-0x26560")
for off in range(0x264A0, 0x26560, 16):
    w("  0x%05X  %-47s  %s" % (off, hx(off, 16), ascii_run(off, 16)))

# ---------- C. 真 ASCII 串（严格版：>=8 字符，全可打印，含至少1个字母） ----------
w()
w("### C. 严格 ASCII 串（长度>=8，全可打印，含字母，尾部 0x19A00-END）")
pat = re.compile(rb'[\x20-\x7e]{8,}')
real = []
for m in pat.finditer(D[0x19A00:]):
    s = m.group()
    if not any(65 <= c <= 90 or 97 <= c <= 122 for c in s):
        continue
    real.append((0x19A00 + m.start(), s.decode('ascii')))
w("  共 %d 条（较上轮 170 条收紧）" % len(real))
for off, s in real[:80]:
    w("    0x%05X  (%2d) %s" % (off, len(s), s))

# ---------- D. ARM Thumb 函数边界 ----------
w()
w("### D. ARM Thumb 函数边界（0x1A000-END）")
# Thumb: PUSH {...,LR} 常见编码 2-byte: B5xx (push {lr,rx}) , 或 32-bit E92D xxxx (push.w {...,lr})
# BX LR = 70 47 ; POP {...,PC} = BDxx 或 E8BD xxxx
starts = []
i = 0x1A000
push16 = Counter()
end16 = Counter()
while i < len(D) - 1:
    hw = D[i] | (D[i+1] << 8)
    if 0xB400 <= hw <= 0xB5FF:
        # push {regs, lr} iff bit8 set  (0xB5xx)
        if (hw & 0x0100) and (hw & 0x00FF):
            starts.append(i)
    i += 2
w("  Thumb 16-bit PUSH{...,LR} (0xB5xx) 出现 %d 次" % len(starts))
# 找成对：push 后最近一次 BX LR / POP{PC}
pairs = 0
sizes = []
for s in starts:
    j = s
    end = None
    while j < min(s + 2000, len(D) - 1):
        hw = D[j] | (D[j+1] << 8)
        if hw == 0x4770:  # bx lr
            end = j + 2; break
        if 0xBD00 <= hw <= 0xBDFF:  # pop {..., pc}
            end = j + 2; break
        j += 2
    if end:
        pairs += 1
        sizes.append(end - s)
w("  其中能找到 BX LR / POP{PC} 收尾的成对函数: %d" % pairs)
if sizes:
    sizes.sort()
    w("  函数长度: 最短 %d  中位 %d  最长 %d  平均 %.0f" %
      (sizes[0], sizes[len(sizes)//2], sizes[-1], sum(sizes)/len(sizes)))
    w("  长度分布(前12): %s" % str(Counter(sizes).most_common(12)))

# ---------- E. printf 调用面 ----------
w()
w("### E. 0x19A00-END 里的数据/常量特征")
seg = D[0x19A00:]
# u32 LE 落在 [0x00010000, 0x00028000) 的（内部地址引用）
refs = Counter()
for i in range(0, len(seg) - 3):
    v = struct.unpack_from('<I', seg, i)[0]
    if 0x10000 <= v < 0x28000:
        refs[v & ~3] += 1
w("  指向 0x10000-0x28000 的 u32 字面量（可能是指针/表引用），top20:")
for v, c in refs.most_common(20):
    w("    0x%05X   x%d" % (v, c))
w("  合计 %d 个对齐地址引用" % len(refs))

# ---------- F. 常量表识别 ----------
w()
w("### F. 0x27000-END 常量表（按 4 字节/2 字节看）")
for off in range(0x27000, len(D) - 3, 4):
    v = struct.unpack_from('<f', D, off)[0]
    if 0.0 < abs(v) < 1e6:
        pass
# 只打印 0x27180-0x271F0 的 float32 视图
w("  float32 视图 0x27180-0x27200:")
for off in range(0x27180, 0x27200, 4):
    v = struct.unpack_from('<f', D, off)[0]
    w("    0x%05X  %-11s = %+.6f" % (off, ' '.join('%02x'%b for b in D[off:off+4]), v))
w("  u16 视图 0x27000-0x27080:")
for off in range(0x27000, 0x27080, 8):
    vals = struct.unpack_from('<4H', D, off)
    w("    0x%05X  %s" % (off, ' '.join('%5d' % v for v in vals)))

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg_parsed', 'tail_mine.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
print('\n'.join(OUT))
