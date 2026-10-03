"""★★ 架构确认：GT7868Q 主体是不是 8051 / MCS-51 代码？

线索（来自官方 gt7868q_gtx8 更新源码）：
  - gtx8_gtx8_update.cpp: "Failed write cfg to xdata"      ← 8051 专有术语
  - gt_update.h:          #define FLASH_BUFFER_ADDR 0xc000 // X8=0XDE24
  - gtx8_gtx8_update.cpp: CFG_START_ADDR 0x60DC / CMD_ADDR 0x60CC   （16 位地址）
  - gt7868q_gt7868q_update.cpp: CFG_START_ADDR 0x96F8
  - GT7868QFirmwareImage : public GTX3FirmwareImage         ← GT 系列共用架构

验证：8051 的「高频操作码」若显著高于随机，即为 8051 代码。
对照：TF100A 段（ARM Cortex-M4F，非 8051）与随机字节应无此偏向。
"""
import os
import collections
import random

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
GQ = d[0x1200:0x19800]
TF = d[0x19800:]
random.seed(7)
RND = bytes(random.randrange(256) for _ in range(len(GQ)))

# 8051 高频/特征操作码
OPCODES = {
    0x74: "MOV A,#imm",
    0x75: "MOV direct,#imm",
    0x78: "MOV R0,#imm", 0x79: "MOV R1,#imm", 0x7A: "MOV R2,#imm", 0x7B: "MOV R3,#imm",
    0x7C: "MOV R4,#imm", 0x7D: "MOV R5,#imm", 0x7E: "MOV R6,#imm", 0x7F: "MOV R7,#imm",
    0x12: "LCALL addr16",
    0x02: "LJMP addr16",
    0x80: "SJMP rel",
    0x22: "RET",
    0x32: "RETI",
    0xC0: "PUSH direct",
    0xD0: "POP direct",
    0xE0: "MOVX A,@DPTR",
    0xF0: "MOVX @DPTR,A",
    0xE4: "CLR A",
    0xF5: "MOV direct,A",
    0x85: "MOV direct,direct",
    0xA3: "INC DPTR",
    0x90: "MOV DPTR,#imm16",
    0xE5: "MOV A,direct",
    0x05: "INC direct",
    0x25: "ADD A,direct",
    0x53: "ANL direct,#imm",
    0x43: "ORL direct,#imm",
}


def hist(seg):
    c = collections.Counter(seg)
    n = len(seg)
    return c, n


print("=" * 100)
print("① 8051 特征操作码密度（次数 / 该值的随机期望）")
print("=" * 100)
print("  %-34s %-12s %-12s %-12s" % ("8051 操作码", "GT7868Q主体", "TF100A(ARM)", "随机字节"))
gq_c, gq_n = hist(GQ)
tf_c, tf_n = hist(TF)
rn_c, rn_n = hist(RND)
rows = []
for op, name in sorted(OPCODES.items()):
    g = gq_c.get(op, 0) / (gq_n / 256)
    t = tf_c.get(op, 0) / (tf_n / 256)
    r = rn_c.get(op, 0) / (rn_n / 256)
    rows.append((g, op, name, t, r))
    print("  0x%02X %-30s %-12.2f %-12.2f %-12.2f" % (op, name, g, t, r))
print()

print("=" * 100)
print("② 汇总：8051 高频码整体偏向（倍数 > 1 表示比随机多）")
print("=" * 100)
hi = [0x74, 0x75, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F]   # MOV 系
ctl = [0x12, 0x02, 0x80, 0x22, 0x32, 0xC0, 0xD0, 0x90, 0xE5, 0xF5]   # 控制/访存
for label, ops in (("MOV 系 (0x74,0x75,0x78-7F)", hi), ("控制/访存 10 条", ctl)):
    g = sum(gq_c.get(o, 0) for o in ops) / (len(ops) * gq_n / 256)
    t = sum(tf_c.get(o, 0) for o in ops) / (len(ops) * tf_n / 256)
    r = sum(rn_c.get(o, 0) for o in ops) / (len(ops) * rn_n / 256)
    print("  %-28s GT7868Q %6.3f×   TF100A %6.3f×   随机 %6.3f×" % (label, g, t, r))
print()

print("=" * 100)
print("③ 关键单值深查：0x75 / 0x74 / 0x12 / 0x22 / 0x90")
print("=" * 100)
for op in (0x75, 0x74, 0x12, 0x22, 0x90, 0x80):
    g = gq_c.get(op, 0)
    t = tf_c.get(op, 0)
    r = rn_c.get(op, 0)
    print("  0x%02X : GT7868Q %5d 次 (%.2f×)  TF100A %5d 次 (%.2f×)  随机 %5d (%.2f×)" % (
        op, g, g / (gq_n / 256), t, t / (tf_n / 256), r, r / (rn_n / 256)))
print()

print("=" * 100)
print("④ 全局字节频率偏移（GT7868Q 主体 vs 均匀）")
print("=" * 100)
# 用卡方近似看哪些字节异常
devs = []
for v in range(256):
    exp = gq_n / 256
    obs = gq_c.get(v, 0)
    devs.append(((obs - exp) / exp, v, obs))
devs.sort(reverse=True)
print("  超出期望最多的 15 个字节：")
for r_, v, o in devs[:15]:
    print("     0x%02X : %6d 次  %+6.1f%%" % (v, o, 100 * r_))
print("  低于期望最多的 10 个字节：")
for r_, v, o in devs[-10:]:
    print("     0x%02X : %6d 次  %+6.1f%%" % (v, o, 100 * r_))
print()

print("=" * 100)
print("⑤ 判定")
print("=" * 100)
hi_g = sum(gq_c.get(o, 0) for o in hi) / (len(hi) * gq_n / 256)
print("  GT7868Q 主体 MOV 系偏向 = %.3f×" % hi_g)
print("  随机基线 = 1.000×；TF100A(ARM) 作为「非 8051」对照")
print()
if hi_g > 1.15:
    print("  ★ MOV 系显著偏高 ⇒ 与 8051 代码特征一致")
else:
    print("  ⚠ MOV 系未显著偏高 ⇒ 需进一步检验（可能是压缩/加密，或非标准 8051 变体）")
