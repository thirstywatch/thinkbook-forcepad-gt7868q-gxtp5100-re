# -*- coding: utf-8 -*-
"""
决定性：0x1E000 用"链式约束"反推指令边界
线索：出现确定度 1.000 的字节链
  d1 ff e7 / e7 ff e7 / 00 ff e7 / dc ff e7  (38 次)
  e7 bd f8   (36 次)
  f8 4a 02   → 第4字节 .698
  bd f8 4a   → 第4字节 .709
方法：把"确定度 1.000 的 3 字节串"当作锚，看它们在文件中的位置关系，
     推断真正的记录/指令周期。
"""
import os, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "region_1E000_chain.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

SEG = data[0x1E000:0x20000]
N = len(SEG)

w("=" * 80)
w("0x1E000 链式约束反推")
w("=" * 80); w()

def find_all(b, pat):
    r = []; i = 0
    while True:
        j = b.find(pat, i)
        if j < 0: break
        r.append(j); i = j + 1
    return r

ANCHORS = [
    (b"\xd1\xff\xe7", "d1 ff e7"),
    (b"\xe7\xff\xe7", "e7 ff e7"),
    (b"\x00\xff\xe7", "00 ff e7"),
    (b"\xdc\xff\xe7", "dc ff e7"),
    (b"\xe7\xbd\xf8", "e7 bd f8"),
    (b"\xbd\xf8\x4a", "bd f8 4a"),
    (b"\xf8\x4a\x02", "f8 4a 02"),
    (b"\xe7\x17\x99", "e7 17 99"),
    (b"\xe7\x17\x98", "e7 17 98"),
    (b"\xc2\xf2\x00", "c2 f2 00"),
]

w("【1】各锚点的位置集合（前 20 个）")
posmap = {}
for pat, nm in ANCHORS:
    p = find_all(SEG, pat)
    posmap[nm] = p
    w("  %-12s ×%-4d  前20: %s" % (nm, len(p), [hex(x) for x in p[:20]]))
w()

w("【2】锚点之间的偏移差（差分），找公共周期")
for nm, p in posmap.items():
    if len(p) < 3: continue
    d = [p[k+1]-p[k] for k in range(len(p)-1)]
    w("  %-12s 差分 Top-8: %s" % (nm, collections.Counter(d).most_common(8)))
w()

w("【3】同一锚点是否反复出现在固定偏移？按 mod 检查")
for nm in ("e7 bd f8", "bd f8 4a", "f8 4a 02", "e7 ff e7"):
    p = posmap[nm]
    if len(p) < 4: continue
    mods = collections.Counter(x % 16 for x in p)
    w("  %-12s mod16 分布: %s" % (nm, sorted(mods.items())))
    mods2 = collections.Counter(x % 64 for x in p)
    w("  %-12s mod64 集中: %s" % ("", mods2.most_common(5)))
w()

w("【4】把 ff e7 出现处按前后字节上下文化（找固定模板）")
p = posmap["e7 ff e7"] + posmap["d1 ff e7"] + posmap["00 ff e7"] + posmap["dc ff e7"]
allff = sorted(set(find_all(SEG, b"\xff\xe7")))
w("  ff e7 总出现 %d 处。前 3 字节的模式分布:" % len(allff))
pre = collections.Counter(SEG[i-3:i] for i in allff if i >= 3)
w("    %s" % ", ".join("%s×%d" % (k.hex(" "), v) for k, v in pre.most_common(10)))
w("  后 3 字节的模式分布:")
post = collections.Counter(SEG[i+2:i+5] for i in allff if i+5 <= N)
w("    %s" % ", ".join("%s×%d" % (k.hex(" "), v) for k, v in post.most_common(10)))
w()

w("【5】关键验证：ff e7 是否等价于 8051 的 MOVX @DPTR,A (0xF0) 之类？")
w("  试把 ff e7 解释为「一字节操作码 + 跨字节」：")
w("    若指令边界偏移 1：... ff | e7 xx | ...  e7 = MOV A,@R1")
w("    若边界偏移 0：ff = MOV R7,A")
w()

w("【6】★ 直接用 8051 SB/SJMP/JMP 目标地址合法性做约束检验")
w("  原理：0x80 SJMP、0x70 JNZ 等相对跳转，其操作数是 **有符号 8 位相对偏移**。")
w("       真代码里这些偏移应集中在 -30..+30（小循环），且跳转落点应落在合法指令边界。")
w("       数据里偏移会均匀散布在 -128..+127。")
callable_offsets = []
for i in range(N-2):
    if SEG[i] in (0x80, 0x70, 0x60, 0x50, 0x40, 0x30, 0x20, 0x10,
                  0x01, 0x21, 0x41, 0x61, 0x81, 0xa1, 0xc1, 0xe1,
                  0x11, 0x31, 0x51, 0x71, 0x91, 0xb1, 0xd1, 0xf1):
        rel = SEG[i+1]
        if rel >= 128: rel -= 256
        callable_offsets.append(rel)
c = collections.Counter(callable_offsets)
w("  相对跳转偏移数量 %d" % len(callable_offsets))
w("  偏移分布: |rel|<=8: %d, 9-16: %d, 17-32: %d, 33-64: %d, 65-127: %d"
  % (sum(v for k, v in c.items() if abs(k) <= 8),
     sum(v for k, v in c.items() if 9 <= abs(k) <= 16),
     sum(v for k, v in c.items() if 17 <= abs(k) <= 32),
     sum(v for k, v in c.items() if 33 <= abs(k) <= 64),
     sum(v for k, v in c.items() if 65 <= abs(k) <= 127)))
# 随机对照
import random
random.seed(7)
rnd = [random.randint(-128, 127) for _ in range(len(callable_offsets))]
cr = collections.Counter(rnd)
w("  随机对照: |rel|<=8: %d(%.3f), 9-16: %d(%.3f), 17-32: %d(%.3f)"
  % (sum(v for k, v in cr.items() if abs(k) <= 8), sum(v for k, v in cr.items() if abs(k) <= 8)/len(rnd),
     sum(v for k, v in cr.items() if 9 <= abs(k) <= 16), sum(1 for k in rnd if 9 <= abs(k) <= 16)/len(rnd),
     sum(v for k, v in cr.items() if 17 <= abs(k) <= 32), sum(1 for k in rnd if 17 <= abs(k) <= 32)/len(rnd)))
w("  0x1E000 实际占比: |rel|<=8: %.3f, 9-16: %.3f, 17-32: %.3f"
  % (sum(v for k, v in c.items() if abs(k) <= 8)/len(callable_offsets),
     sum(v for k, v in c.items() if 9 <= abs(k) <= 16)/len(callable_offsets),
     sum(v for k, v in c.items() if 17 <= abs(k) <= 32)/len(callable_offsets)))
w()

w("【7】真代码 0x00000 上的同一检验（作为正对照）")
S0 = data[0x00000:0x01000]
co = []
for i in range(len(S0)-2):
    if S0[i] in (0x80,0x70,0x60,0x50,0x40,0x30,0x20,0x10,
                 0x01,0x21,0x41,0x61,0x81,0xa1,0xc1,0xe1,
                 0x11,0x31,0x51,0x71,0x91,0xb1,0xd1,0xf1):
        rel = S0[i+1]
        if rel >= 128: rel -= 256
        co.append(rel)
if co:
    w("  rel 数量 %d,  |rel|<=8 占比 %.3f  中位 |rel| = %d"
      % (len(co), sum(1 for k in co if abs(k) <= 8)/len(co),
         sorted(abs(k) for k in co)[len(co)//2]))
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
