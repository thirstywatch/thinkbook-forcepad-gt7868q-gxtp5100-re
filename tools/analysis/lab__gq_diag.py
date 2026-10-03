"""GT7868Q 主体质量诊断：是 Cortex-M0(Thumb-1) 代码，还是数据/表？

判据设计：
 D1 单字节分布 vs 均匀 —— 代码有偏（0x00/0xFF/常见操作码），数据表另有偏
 D2 字面量池证据：Thumb-1 用 LDR Rd,[PC,#imm8*4]（编码 XX 48..4F）加载 32 位常量
    —— Cortex-M0 无 MOVW/MOVT，若这段是真 M0 代码，该模式必密集
 D3 函数结构：POP {..,PC}(BC/BD) 之后应紧跟 PUSH(B4/B5)
 D4 对照：TF100A（确认 Thumb-2 代码）与「随机字节」做上下界
"""
import os
import collections
import random
import capstone
from capstone import *

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()

GQ = d[0x1200:0x19800]
TF = d[0x19800:]
random.seed(5)
RND = bytes(random.randrange(256) for _ in range(len(GQ)))


def stat(name, seg):
    n = len(seg)
    c = collections.Counter(seg)
    # D2: LDR Rd,[PC,#imm]  —— 第一个半字 0x48xx|Rd<<8，小端存为 [imm8][48..4F]
    ldrpc = sum(1 for i in range(n - 1) if 0x48 <= seg[i + 1] <= 0x4F)
    # LDR.W / 其他 pc 相对
    push = sum(1 for i in range(n - 1) if seg[i] in (0xB4, 0xB5))
    pop = sum(1 for i in range(n - 1) if seg[i] in (0xBC, 0xBD))
    bxlr = seg.count(b"\x70\x47")
    movw = sum(1 for i in range(n - 1) if 0x40 <= seg[i] <= 0x4F and seg[i + 1] == 0xF2)
    zero = 100 * seg.count(0) / n
    ff = 100 * seg.count(0xFF) / n
    return dict(n=n, ldrpc=ldrpc, push=push, pop=pop, bxlr=bxlr, movw=movw, zero=zero, ff=ff)


print("=" * 100)
print("① 特征密度对照（每 KB）")
print("=" * 100)
print("  %-16s %-9s %-9s %-9s %-9s %-9s %-8s %-8s" % (
    "样本", "LDR_PC", "PUSH", "POP", "BXLR", "MOVW", "0x00%", "0xFF%"))
rows = {}
for name, seg in (("GT7868Q主体", GQ), ("TF100A(代码)", TF), ("随机字节", RND)):
    s = stat(name, seg)
    rows[name] = s
    k = s["n"] / 1024
    print("  %-16s %-9.1f %-9.1f %-9.1f %-9.1f %-9.1f %-8.2f %-8.2f" % (
        name, s["ldrpc"] / k, s["push"] / k, s["pop"] / k,
        s["bxlr"] / k, s["movw"] / k, s["zero"], s["ff"]))
print()
print("  ★ 判读：若 GT7868Q主体 的 LDR_PC 与 TF100A 同量级 ⇒ 同为 Thumb 代码（只是 M0 vs M4）")
print("         若两者都远高于『随机字节』⇒ 存在指令结构（不是数据）")
print()

print("=" * 100)
print("② 函数结构检验：POP{..,PC} 之后 8 字节内是否有 PUSH")
print("=" * 100)
for name, seg in (("GT7868Q主体", GQ), ("TF100A(代码)", TF), ("随机字节", RND)):
    pops = [i for i in range(len(seg) - 1) if seg[i] in (0xBC, 0xBD)]
    near = sum(1 for i in pops if any(seg[i + j] in (0xB4, 0xB5) for j in range(2, 12)))
    print("  %-16s POP %5d 个，其中 %5d 个后随 PUSH = %.1f%%" % (
        name, len(pops), near, 100 * near / max(1, len(pops))))
print()

print("=" * 100)
print("③ 字面量池检验：LDR Rd,[PC,#imm]（XX 48..4F）的地址分布")
print("=" * 100)
for name, seg, base in (("GT7868Q主体", GQ, 0x1200), ("TF100A(代码)", TF, 0x19800)):
    pos = [i for i in range(len(seg) - 1) if 0x48 <= seg[i + 1] <= 0x4F]
    print("  %-16s %d 处" % (name, len(pos)))
    if pos:
        gaps = [pos[i + 1] - pos[i] for i in range(min(400, len(pos) - 1))]
        hist = collections.Counter(min(g // 16, 20) for g in gaps)
        print("     间隔分布(×16B桶): %s" % sorted(hist.items())[:12])
print()

print("=" * 100)
print("④ 直接反汇编「最像代码」的两个低熵块")
print("=" * 100)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
for off, why in ((0x0C200, "熵 6.19"), (0x0D600, "熵 6.20"), (0x13A00, "熵 6.93")):
    print("  --- 主体偏移 0x%05X（%s），基址取 0x08000000+off ---" % (off, why))
    cnt = 0
    for i in md.disasm(d[off:off + 0x60], 0x08000000 + off):
        print("    %08X  %-18s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
        cnt += 1
        if cnt >= 18:
            break
    print()

print("=" * 100)
print("⑤ 对照：TF100A 已知好代码在同一流程下的样子（0x203C6）")
print("=" * 100)
cnt = 0
for i in md.disasm(d[0x203C6:0x203C6 + 0x60], 0x0800BBC6):
    print("    %08X  %-18s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
    cnt += 1
    if cnt >= 18:
        break
