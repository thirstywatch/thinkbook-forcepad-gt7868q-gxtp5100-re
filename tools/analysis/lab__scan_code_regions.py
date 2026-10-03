"""最后一步：主体里是否存在「像 8051 代码」的区域？

Turbo51 与 8051 二进制兼容 ⇒ 若主体含代码，应有局部区域呈现正常 C51 输出特征：
  RET(0x22) 1-3% · LCALL(0x12) 1-3% · MOV A,#imm(0x74) 3-8% · MOV direct,#imm(0x75) 2-6%
本脚本逐 4 KiB 区域扫描这些指标，并与「全局/随机」对照，找出候选代码区。
"""
import os
import collections

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()
seg = d[0x1200:0x19A00]        # 加扰区（含 0x19800-0x19A00 那段）


def metrics(b):
    n = len(b)
    if n == 0:
        return None
    return {
        "RET": 100 * b.count(0x22) / n,
        "LCALL": 100 * b.count(0x12) / n,
        "MOVidx": 100 * b.count(0x74) / n,       # MOV A,#imm
        "MOVdir": 100 * b.count(0x75) / n,       # MOV direct,#imm
        "MOVAd": 100 * b.count(0xE5) / n,        # MOV A,direct
        "MOVXA": 100 * b.count(0xE0) / n,        # MOVX A,@DPTR
        "PUSH": 100 * b.count(0xC0) / n,
        "POP": 100 * b.count(0xD0) / n,
        "zero": 100 * b.count(0) / n,
    }


print("=" * 108)
print("① 逐 4 KiB 区域的 8051 指标（找「像 C51 输出」的区域）")
print("=" * 108)
print("  %-9s %-7s %-7s %-7s %-7s %-7s %-7s %-7s %-7s %s" % (
    "偏移", "RET", "LCALL", "MOV74", "MOV75", "MOVE5", "MOVX", "PUSH", "POP", "0x00%"))
rows = []
for i in range(0, len(seg), 0x1000):
    b = seg[i:i + 0x1000]
    if len(b) < 512:
        break
    m = metrics(b)
    score = m["RET"] + m["LCALL"] + m["MOVidx"] + m["MOVdir"]
    rows.append((score, 0x1200 + i, m))
allm = metrics(seg)
for score, off, m in sorted(rows, reverse=True)[:20]:
    print("  0x%05X  %-7.3f %-7.3f %-7.3f %-7.3f %-7.3f %-7.3f %-7.3f %-7.3f %-6.1f  sig=%.2f" % (
        off, m["RET"], m["LCALL"], m["MOVidx"], m["MOVdir"], m["MOVAd"], m["MOVXA"],
        m["PUSH"], m["POP"], m["zero"], score))
print()
print("  全段平均：RET %.3f  LCALL %.3f  MOV74 %.3f  MOV75 %.3f  →  sig=%.2f" % (
    allm["RET"], allm["LCALL"], allm["MOVidx"], allm["MOVdir"],
    allm["RET"] + allm["LCALL"] + allm["MOVidx"] + allm["MOVdir"]))
print()

print("=" * 108)
print("② 参照：真 C51 输出的典型值（文献/经验）")
print("=" * 108)
print("  RET 1-3%   LCALL 1-3%   MOV A,#imm 3-8%   MOV direct,#imm 2-6%   →  sig 7-20")
print("  随机字节：sig ≈ %.2f" % (
    100 * 2 / 256 + 100 * 2 / 256 + 100 * 2 / 256 + 100 * 2 / 256))
print()

print("=" * 108)
print("③ 最强候选区 0x%05X 的 8051 反汇编（人眼终判）" % sorted(rows, reverse=True)[0][1])
print("=" * 108)
THREE = {0x02, 0x12, 0x90, 0x75, 0x85, 0x43, 0x53, 0x63, 0xB5, 0xD5,
         0xB4, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
         0x10, 0x20, 0x30}
MX = {0x22: "RET", 0x32: "RETI", 0x02: "LJMP", 0x12: "LCALL", 0x74: "MOV A,#",
      0x75: "MOV dir,#", 0xE5: "MOV A,dir", 0xF5: "MOV dir,A", 0x90: "MOV DPTR,#",
      0xE0: "MOVX A,@DPTR", 0xF0: "MOVX @DPTR,A", 0xC0: "PUSH dir", 0xD0: "POP dir",
      0x80: "SJMP", 0x00: "NOP", 0x24: "ADD A,#", 0x25: "ADD A,dir", 0x05: "INC dir",
      0x15: "DEC dir", 0xA3: "INC DPTR", 0xE4: "CLR A", 0x04: "INC A", 0x14: "DEC A"}
top = sorted(rows, reverse=True)[0][1]
b = d[top:top + 0x60]
p = 0
while p < len(b):
    op = b[p]
    ln = 3 if op in THREE else (2 if op in (0x74, 0x24, 0x34, 0x44, 0x54, 0x64, 0x94, 0xE5,
                                            0xF5, 0x05, 0x15, 0x25, 0x35, 0x45, 0x55, 0x65,
                                            0x95, 0xC5, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D,
                                            0x7E, 0x7F, 0x80, 0x40, 0x50, 0x60, 0x70, 0xC0,
                                            0xD0, 0x10, 0x20, 0x30) else 1)
    name = MX.get(op, "?%02X" % op)
    extra = ""
    if ln >= 2:
        extra = "0x%02X" % b[p + 1]
    if ln == 3:
        extra = "0x%04X" % ((b[p + 1] << 8) | b[p + 2])
    print("   %05X  %-14s %-14s %s" % (top + p, b[p:p + ln].hex(), name, extra))
    p += ln
