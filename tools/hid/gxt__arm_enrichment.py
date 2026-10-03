# -*- coding: utf-8 -*-
"""
量化 "0x1E000 里的 ARM 片段是真的吗" —— 富集倍数检验
原理：把候选 ARM 特征串在(固件全文件 / 0x1E000区 / 随机对照)中计数，
     算富集倍数。真代码里功能序列应有 10^2~10^3 倍富集；
     偶然匹配只有 10^0~10^1 倍。
"""
import os, collections

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed")
OUT = os.path.join(OUTDIR, "arm_enrichment.txt")
data = open(FW, "rb").read()
lines = []
def w(s=""):
    lines.append(s); print(s)

SEG = data[0x1E000:0x20000]
N = len(SEG)

w("=" * 80)
w("0x1E000 中 ARM 特征的富集倍数检验")
w("=" * 80); w()
w("  判据：2 字节串在 N 字节区内的随机期望次数 = N / 65536")
w("       富集倍数 = 实测次数 / 期望次数")
w("       真代码里的功能序列 ：富集 10^2 以上")
w("       偶然匹配          ：富集 10^0~10^1")
w()

def count_all(b, pat):
    n = 0; i = 0
    while True:
        j = b.find(pat, i)
        if j < 0: break
        n += 1; i = j + 1
    return n

CAND = [
    (b"\x70\x47", "ARM: BX LR (函数返回)"),
    (b"\x80\xb5", "ARM: PUSH {R7,LR} (函数序言)"),
    (b"\x00\xbf", "ARM: NOP"),
    (b"\x08\xb0", "ARM: ADD SP,#32"),
    (b"\xbf\xf3\x4f\x8f", "ARM: DMB ISH"),
    (b"\x2d\xe9", "ARM: PUSH.W 前缀"),
    (b"\xbd\xe8", "ARM: POP.W 前缀"),
    (b"\x4f\xf0", "ARM: MOV.W Rd,#imm"),
    (b"\x00\xf0", "ARM: BL 前缀(thumb2)"),
    (b"\xdf\xf8", "ARM: LDR.W literal"),
    (b"\x90\x47", "ARM: BLX R2"),
    (b"\x30\x47", "ARM: BLX R6"),
    # 8051 真特征
    (b"\x22\x00", "8051: RET + nop"),
    (b"\x12\x00", "8051: LCALL 0x0000"),
    # 无关对照
    (b"\x7f\x7f", "对照: 7f 7f"),
    (b"\xff\xff", "对照: ff ff"),
    (b"\x00\x00", "对照: 00 00"),
]

w("  %-28s %8s %10s %10s %8s" % ("模式", "实测", "随机期望", "富集倍数", "判定"))
w("  " + "-" * 72)
for pat, nm in CAND:
    cnt = count_all(SEG, pat)
    exp = N / (256 ** len(pat)) if len(pat) == 2 else N / (256 ** len(pat))
    enr = cnt / exp if exp > 0 else float("inf")
    verdict = "真信号" if enr >= 50 else ("弱" if enr >= 5 else "噪声")
    w("  %-28s %8d %10.3f %10.1f %8s" % (nm, cnt, exp, enr, verdict))
w()

w("【关键判断】函数序言/返回的配对率")
push = count_all(SEG, b"\x80\xb5")
pop = count_all(SEG, b"\xbd\xe8")
bx = count_all(SEG, b"\x70\x47")
w("  PUSH {R7,LR} = %d   POP.W 前缀 = %d   BX LR = %d" % (push, pop, bx))
w("  真 ARM 代码应有 PUSH ≈ POP ≈ BX LR，且数量级在 (代码字节数/30) 量级")
w("  此处 8 KB 若是 ARM 代码，应约 %d 个函数" % (8192 // 60))
w()

w("【决定性对照】同一批模式在'100%% 确定是 ARM Thumb 代码'上的计数")
# 用固件以外的 Windows 系统 DLL 里的 ARM 代码不现实；改用 x86 无关。
# 换法：把模式放在"已知 8051 真代码区 0x00000"上跑一次
REALCODE = data[0x00000:0x01000]
w("  0x00000（4096 B, 已确证 8051 真代码）:")
for pat, nm in CAND[:4]:
    cnt = count_all(REALCODE, pat)
    exp = len(REALCODE) / (256 ** len(pat))
    w("    %-28s 实测 %3d  富集 %.1f" % (nm, cnt, cnt/exp if exp else 0))
w()

w("【补充】0x1E000 中那些'像指令'的固定对，究竟是几字节周期？")
# 用 c2f2 作锚，看后续字节的确定性链
pos = [i for i in range(N-1) if SEG[i:i+2] == b"\xc2\xf2"]
w("  c2 f2 之后 6 字节的取值分布:")
for k in range(2, 8):
    c = collections.Counter(SEG[p+k] for p in pos if p+k < N)
    top = c.most_common(3)
    w("    +%d : %s   (确定度 %.3f)" % (k,
      ", ".join("0x%02X:%d" % (b, n) for b, n in top),
      top[0][1]/sum(c.values()) if c else 0))
w()

w("【补充】把 c2f2 当作'记录分隔符'，看记录长度分布")
d = sorted(set(pos[k+1]-pos[k] for k in range(len(pos)-1)))
w("  相邻间距不同取值: %s" % d)
w()

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n-> %s" % OUT)
