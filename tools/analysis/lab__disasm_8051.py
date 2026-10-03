"""8051 / Turbo-51 反汇编器（自包含，用于直接观察 GT7868Q 主体）。

架构已确认：Turbo 51（增强型 8051）
  证据链：GT911 数据手册框图 "Turbo 51(M)/Turbo 51(S)"（Goodix GT 系列同架构）
        + 官方源码 gtx8/gtx3/gt7868q_update.cpp 里的 "xdata"
        + gt_update.h: FLASH_BUFFER_ADDR 0xc000（16 位 xdata）
        + GTx8Device : public GTx3Device / GT7868QFirmwareImage : public GTX3FirmwareImage
"""
import os
import collections

HERE = r"<LAB>\touchpad-lab\poc\anchor-hunt"
d = open(os.path.join(HERE, "GT7868Q_plain.bin"), "rb").read()

# ── 8051 指令表：mnemonic 模板 + 长度 ──
# 用规则生成，再补特例
MN = [None] * 256
LN = [1] * 256


def setop(op, mn, ln):
    MN[op] = mn
    LN[op] = ln


def gen():
    # x0 组
    setop(0x00, "NOP", 1)
    for r in range(8):
        setop(0x00 + 0x08 + r, "INC R%d" % r, 1)
        setop(0x10 + 0x08 + r, "DEC R%d" % r, 1)
        setop(0x20 + 0x08 + r, "ADD A,R%d" % r, 1)
        setop(0x30 + 0x08 + r, "ADDC A,R%d" % r, 1)
        setop(0x40 + 0x08 + r, "ORL A,R%d" % r, 1)
        setop(0x50 + 0x08 + r, "ANL A,R%d" % r, 1)
        setop(0x60 + 0x08 + r, "XRL A,R%d" % r, 1)
        setop(0x70 + 0x08 + r, "MOV R%d,#imm" % r, 2)
        setop(0x80 + 0x08 + r, "MOV direct,R%d" % r, 2)
        setop(0xA0 + 0x08 + r, "MOV R%d,direct" % r, 2)
        setop(0xB0 + 0x08 + r, "CJNE R%d,#imm,rel" % r, 3)
        setop(0xC0 + 0x08 + r, "XCH A,R%d" % r, 1)
        setop(0xD0 + 0x08 + r, "DJNZ R%d,rel" % r, 2)
        setop(0xE0 + 0x08 + r, "MOV A,R%d" % r, 1)
        setop(0xF0 + 0x08 + r, "MOV R%d,A" % r, 1)
    for r in range(2):
        setop(0x06 + r, "INC @R%d" % r, 1)
        setop(0x16 + r, "DEC @R%d" % r, 1)
        setop(0x26 + r, "ADD A,@R%d" % r, 1)
        setop(0x36 + r, "ADDC A,@R%d" % r, 1)
        setop(0x46 + r, "ORL A,@R%d" % r, 1)
        setop(0x56 + r, "ANL A,@R%d" % r, 1)
        setop(0x66 + r, "XRL A,@R%d" % r, 1)
        setop(0x76 + r, "MOV @R%d,#imm" % r, 2)
        setop(0x86 + r, "MOV direct,@R%d" % r, 2)
        setop(0xA6 + r, "MOV @R%d,direct" % r, 2)
        setop(0xB6 + r, "CJNE @R%d,#imm,rel" % r, 3)
        setop(0xC6 + r, "XCH A,@R%d" % r, 1)
        setop(0xD6 + r, "XCHD A,@R%d" % r, 1)
        setop(0xE6 + r, "MOV A,@R%d" % r, 1)
        setop(0xF6 + r, "MOV @R%d,A" % r, 1)
    setop(0x03, "RR A", 1); setop(0x13, "RRC A", 1)
    setop(0x23, "RL A", 1); setop(0x33, "RLC A", 1)
    setop(0x04, "INC A", 1); setop(0x14, "DEC A", 1)
    setop(0x24, "ADD A,#imm", 2); setop(0x34, "ADDC A,#imm", 2)
    setop(0x44, "ORL A,#imm", 2); setop(0x54, "ANL A,#imm", 2)
    setop(0x64, "XRL A,#imm", 2); setop(0x74, "MOV A,#imm", 2)
    setop(0x84, "DIV AB", 1); setop(0x94, "SUBB A,#imm", 2)
    setop(0xA4, "MUL AB", 1); setop(0xB4, "CJNE A,#imm,rel", 3)
    setop(0xC4, "SWAP A", 1); setop(0xD4, "DA A", 1)
    setop(0xE4, "CLR A", 1); setop(0xF4, "CPL A", 1)
    setop(0x05, "INC direct", 2); setop(0x15, "DEC direct", 2)
    setop(0x25, "ADD A,direct", 2); setop(0x35, "ADDC A,direct", 2)
    setop(0x45, "ORL A,direct", 2); setop(0x55, "ANL A,direct", 2)
    setop(0x65, "XRL A,direct", 2); setop(0x75, "MOV direct,#imm", 3)
    setop(0x85, "MOV direct,direct", 3); setop(0x95, "SUBB A,direct", 2)
    setop(0xA5, "(reserved)", 1); setop(0xB5, "CJNE A,direct,rel", 3)
    setop(0xC5, "XCH A,direct", 2); setop(0xD5, "DJNZ direct,rel", 3)
    setop(0xE5, "MOV A,direct", 2); setop(0xF5, "MOV direct,A", 2)
    setop(0x02, "LJMP addr16", 3); setop(0x12, "LCALL addr16", 3)
    setop(0x22, "RET", 1); setop(0x32, "RETI", 1)
    setop(0x42, "ORL direct,A", 2); setop(0x52, "ANL direct,A", 2)
    setop(0x62, "XRL direct,A", 2); setop(0x72, "ORL C,bit", 2)
    setop(0x82, "ANL C,bit", 2); setop(0x92, "MOV bit,C", 2)
    setop(0xA2, "MOV C,bit", 2); setop(0xB2, "CPL bit", 2)
    setop(0xC2, "CLR bit", 2); setop(0xD2, "SETB bit", 2)
    setop(0x43, "ORL direct,#imm", 3); setop(0x53, "ANL direct,#imm", 3)
    setop(0x63, "XRL direct,#imm", 3); setop(0x73, "JMP @A+DPTR", 1)
    setop(0x83, "MOVC A,@A+PC", 1); setop(0x93, "MOVC A,@A+DPTR", 1)
    setop(0xA3, "INC DPTR", 1); setop(0xB3, "CPL C", 1)
    setop(0xC3, "CLR C", 1); setop(0xD3, "SETB C", 1)
    setop(0x10, "JBC bit,rel", 3); setop(0x20, "JB bit,rel", 3)
    setop(0x30, "JNB bit,rel", 3); setop(0x40, "JC rel", 2)
    setop(0x50, "JNC rel", 2); setop(0x60, "JZ rel", 2)
    setop(0x70, "JNZ rel", 2); setop(0x80, "SJMP rel", 2)
    setop(0x90, "MOV DPTR,#imm16", 3)
    setop(0xE0, "MOVX A,@DPTR", 1); setop(0xF0, "MOVX @DPTR,A", 1)
    setop(0xE2, "MOVX A,@R0", 1); setop(0xE3, "MOVX A,@R1", 1)
    setop(0xF2, "MOVX @R0,A", 1); setop(0xF3, "MOVX @R1,A", 1)
    setop(0xC0, "PUSH direct", 2); setop(0xD0, "POP direct", 2)
    setop(0x00, "NOP", 1)
    # AJMP / ACALL 的 x1 形式（2 字节）
    for h in range(16):
        op = (h * 0x10 + 0x01) & 0xFF
        if op == 0x01 or (op & 0x0F) == 0x01:
            if MN[op] is None:
                setop(op, "AJMP/ACALL addr11", 2)
    for op in range(256):
        if MN[op] is None:
            setop(op, "?%02X" % op, 1)


gen()


def disasm(seg, base=0, n=40):
    out = []
    p = 0
    while p < len(seg) and len(out) < n:
        op = seg[p]
        ln = LN[op]
        bs = seg[p:p + ln]
        mn = MN[op]
        # 补操作数
        if "addr16" in mn and ln == 3:
            mn = mn.replace("addr16", "#0x%04X" % ((bs[1] << 8) | bs[2]))
        elif "imm16" in mn and ln == 3:
            mn = mn.replace("imm16", "#0x%04X" % ((bs[1] << 8) | bs[2]))
        elif "addr11" in mn and ln == 2:
            a11 = ((op & 0xE0) << 3) | bs[1]
            mn = mn.replace("addr11", "#0x%04X" % a11)
        elif "imm" in mn and ln == 2:
            mn = mn.replace("imm", "#0x%02X" % bs[1])
        if "direct" in mn and ln >= 2:
            mn = mn.replace("direct", "0x%02X" % bs[1], 1)
        if "rel" in mn and ln >= 2:
            off = bs[-1]
            if off > 127:
                off -= 256
            mn = mn.replace("rel", "#0x%04X" % ((base + p + ln + off) & 0xFFFF))
        if "bit" in mn and ln == 2:
            mn = mn.replace("bit", "0x%02X" % bs[1])
        out.append((base + p, bs, mn))
        p += ln
    return out


print("=" * 100)
print("① GT7868Q 主体 直接反汇编（Turbo 51）")
print("=" * 100)
for off in (0x1200, 0x2000, 0x0C200, 0x12000):
    print("  ── 主体偏移 0x%05X ──" % off)
    for a, bs, mn in disasm(d[off:off + 0x80], base=off, n=26):
        print("     %05X  %-12s %s" % (a, bs.hex(), mn))
    print()

print("=" * 100)
print("② 对照：TF100A 段（ARM 代码）用 8051 表解释 —— 应明显不合理")
print("=" * 100)
for a, bs, mn in disasm(d[0x203C6:0x203C6 + 0x60], base=0x203C6, n=18):
    print("     %05X  %-12s %s" % (a, bs.hex(), mn))
print()

print("=" * 100)
print("③ 全局统计：主体里各指令出现频率（按长度表推进，统计「指令」而非字节）")
print("=" * 100)
p = 0
cnt = collections.Counter()
nins = 0
while p < len(d[0x1200:0x19800]):
    op = d[0x1200 + p]
    cnt[MN[op].split()[0]] += 1
    p += LN[op]
    nins += 1
print("  共推出 %d 条「指令」，Top 25 助记符：" % nins)
for k, v in cnt.most_common(25):
    print("     %-18s %6d  (%.2f%%)" % (k, v, 100 * v / nins))
