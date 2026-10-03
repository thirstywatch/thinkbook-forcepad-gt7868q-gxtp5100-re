"""定位 GT7868Q 的代码段：Thumb-2 特征密度扫描 + capstone 质量校验。

已知 TF100A 段（容器 0x19A00+）是**确认的 Cortex-M4F 代码**（asm.txt 里
0x0800BBC6 处有 movw/movt/ldrb/vldr/vsub.f32 的完整浮点流程）。
⇒ 用它做「Thumb-2 代码」的标定基准，再拿同一指标扫 GT7868Q 主体。

Thumb-2 特征（小端内存字节序）：
  MOVW rN,#imm16  →  第一个半字 0xF240|i<<10|imm4  ⇒ 内存字节  4X F2
  MOVT rN,#imm16  →  第一个半字 0xF2C0|i<<10|imm4  ⇒ 内存字节  CX F2
  PUSH {...}      →  B4 xx / B5 xx（含 LR）
  POP  {...}      →  BC xx / BD xx
  BX LR           →  70 47
"""
import os
import collections
import capstone
from capstone import *

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
RAW = open(os.path.join(HERE, "GT7868Q_scramble_key.bin"), "rb").read()

TF_S, TF_E = 0x19800, len(d)          # TF100A 段（确认 Thumb 代码）
GQ_S, GQ_E = 0x1200, 0x19800          # GT7868Q 主体（已解密）


def feats(seg):
    n = len(seg)
    movw = sum(1 for i in range(n - 1) if 0x40 <= seg[i] <= 0x4F and seg[i + 1] == 0xF2)
    movt = sum(1 for i in range(n - 1) if 0xC0 <= seg[i] <= 0xCF and seg[i + 1] == 0xF2)
    push = sum(1 for i in range(n - 1) if seg[i] in (0xB4, 0xB5) and (seg[i + 1] & 0x01) == 0)
    pop = sum(1 for i in range(n - 1) if seg[i] in (0xBC, 0xBD))
    bxlr = seg.count(b"\x70\x47")
    return movw, movt, push, pop, bxlr


print("=" * 94)
print("① 标定：TF100A 段（确认 Cortex-M4F 代码）的特征密度")
print("=" * 94)
tf = d[TF_S:TF_E]
m, mt, pu, po, bx = feats(tf)
L = len(tf)
print("  段长 %d B" % L)
print("  MOVW(4X F2)  %5d  密度 %.1f/KB" % (m, 1000 * m / L))
print("  MOVT(CX F2)  %5d  密度 %.1f/KB" % (mt, 1000 * mt / L))
print("  PUSH(B4/B5)  %5d  密度 %.1f/KB" % (pu, 1000 * pu / L))
print("  POP (BC/BD)  %5d  密度 %.1f/KB" % (po, 1000 * po / L))
print("  BX LR(70 47) %5d  密度 %.1f/KB" % (bx, 1000 * bx / L))
print()

print("=" * 94)
print("② GT7868Q 主体（已解密）同指标")
print("=" * 94)
gq = d[GQ_S:GQ_E]
m2, mt2, pu2, po2, bx2 = feats(gq)
L2 = len(gq)
print("  段长 %d B" % L2)
print("  MOVW(4X F2)  %5d  密度 %.1f/KB" % (m2, 1000 * m2 / L2))
print("  MOVT(CX F2)  %5d  密度 %.1f/KB" % (mt2, 1000 * mt2 / L2))
print("  PUSH(B4/B5)  %5d  密度 %.1f/KB" % (pu2, 1000 * pu2 / L2))
print("  POP (BC/BD)  %5d  密度 %.1f/KB" % (po2, 1000 * po2 / L2))
print("  BX LR(70 47) %5d  密度 %.1f/KB" % (bx2, 1000 * bx2 / L2))
print()
print("  → 若两组量级相近 ⇒ GT7868Q 主体同样是 Thumb-2 代码")
print()

print("=" * 94)
print("③ 逐 4 KiB 扫 GT7868Q 全文件的「Thumb-2 特征密度」—— 定位代码段")
print("=" * 94)
print("  %-10s %-8s %-8s %-8s %-8s %s" % ("偏移", "MOVW", "PUSH", "POP", "BXLR", "判读"))
for s in range(0, len(d), 0x1000):
    seg = d[s:s + 0x1000]
    if len(seg) < 512:
        break
    a, b, c, e, f = feats(seg)
    score = a * 3 + f * 2 + b + e
    tag = "★代码" if score > 60 else ("代码?" if score > 25 else ("" if score > 8 else "数据/空"))
    print("  0x%05X   %-8d %-8d %-8d %-8d %s" % (s, a, c, e, f, tag))
print()

print("=" * 94)
print("④ 用 capstone 反汇编 GT7868Q 主体开头，检查指令合理性")
print("=" * 94)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
for label, off, base in (("GT7868Q 主体 @0x1200", 0x1200, 0x08000000),
                         ("GT7868Q 主体 @0x1200 (基址0)", 0x1200, 0)):
    print("  --- %s ---" % label)
    cnt = 0
    for i in md.disasm(d[off:off + 0x100], base + off):
        print("    %08X: %-9s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
        cnt += 1
        if cnt >= 20:
            break
    print()

print("=" * 94)
print("⑤ 对照：TF100A 段 0x0800BBC6 处（已知好代码）用同一流程反汇编")
print("=" * 94)
# asm.txt 说 0x0800BBC6 是好代码；反推它在容器里的文件偏移
# TF100A 段起点文件偏移 0x19800 ↔ 地址 0x08005000（由 asm.txt 首行推得）
tf_base_addr = 0x08005000
tf_base_off = 0x19800
target_addr = 0x0800BBC6
target_off = tf_base_off + (target_addr - tf_base_addr)
print("  推算文件偏移 = 0x%05X" % target_off)
cnt = 0
for i in md.disasm(d[target_off:target_off + 0x60], target_addr):
    print("    %08X: %-9s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
    cnt += 1
    if cnt >= 16:
        break
