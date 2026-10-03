"""verify-B/deep1.py — 深挖 I2C1 代码簇：
(a) 用 capstone 强制 32 位解码访问 0x40005400 的每条访存，给出确切寄存器与 CR1 位
(b) 精确列出 movw #0x5400 → movt #0x4000 之后的寄存器写，还原 CR1/CR2/CCR 值
(c) 找出所有对 I2C1 空间的 load/store 站点（含 base+offset 形式）
"""
import struct, sys, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
md32 = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md32.detail = True

# 线性解码（自然）
ALL = []
a = A_LO
while a <= A_HI:
    ok = False
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; ok = True; break
    if not ok: a += 2
AT = {i.address: i for i in ALL}

I2C1 = 0x40005400
I2CREG = {0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",
          0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}
CR1BIT = {0x0001:"PE",0x0002:"SMBUS",0x0004:"SMBTYPE",0x0008:"ENARP",0x0010:"ENPEC",
          0x0020:"ENGC",0x0040:"NOSTRETCH",0x0080:"START",0x0100:"STOP",0x0200:"ACK",
          0x0400:"POS",0x0800:"PEC",0x1000:"ALERT",0x2000:"SWRST"}
SR1BIT = {0x0001:"SB",0x0002:"ADDR",0x0004:"BTF",0x0008:"ADD10",0x0010:"STOPF",
          0x0040:"RXNE",0x0080:"TXE",0x0100:"GENCALL",0x0200:"DUALF",0x0400:"PECERR",
          0x0800:"OVR",0x1000:"AF",0x2000:"ARLO",0x4000:"BERR"}
SR2BIT = {0x0001:"MSL",0x0002:"BUSY",0x0004:"TRA",0x0008:"RD_WRN",0x0010:"TXE",
          0x0020:"DUALF",0x0080:"GENCALL",0x0100:"SMBHOST",0x0200:"DUALF2",0x0400:"PEC"}

def force32(a):
    """从 a 起强制按 32 位解码（hack：让 capstone 认为它是 32 位）
    做法：用 .w 提示 —— capstone 无该接口，改用直接读半字并手工识别常见 32 位编码。
    这里改用：正常解码若得到 16 位指令但字节流显示是 32 位前缀，则跳过。
    简化：直接尝试把 a 当成 32 位指令的开始（movs/add.w/ldr.w 等均以 11101/11110 开头）
    """
    hw = struct.unpack_from("<H", data, off(a))[0]
    if (hw >> 11) in (0b11101, 0b11110, 0b11111):
        # 32 位指令 —— 正常解码即为 32 位
        for ins in md32.disasm(data[off(a):off(a)+4], a):
            return ins
    return AT.get(a)

print("=" * 82)
print("[A] 访问 I2C1(0x40005400) 空间的所有 movw/movt 物化点 —— 精确后续 12 条指令")
print("    （用「强制 32 位」读法绕过 capstone 把 str r1,[r0] 解成 16 位 str 的问题）")
sites = [i for i in ALL if i.mnemonic == "movw" and len(i.operands) == 2
         and i.operands[1].type == ARM_OP_IMM and (i.operands[1].imm & 0xFFFF) == 0x5400]
for s in sites:
    idx = ALL.index(s)
    seq = ALL[idx:idx+8]
    # 判断是否配 0x4000 / 0x4001
    tag = ""
    for x in seq[:4]:
        if x.mnemonic == "movt" and len(x.operands)==2 and x.operands[1].type==ARM_OP_IMM:
            tag = "0x%08X" % (((s.operands[1].imm & 0xFFFF) | (x.operands[1].imm << 16)) & 0xFFFFFFFF)
    if tag not in ("0x40005400", "0x40015400"): continue
    print("\n  ===== movw #0x5400 @ %08X  (还原基址 %s) =====" % (s.address, tag))
    for k in range(0, 14):
        if idx + k >= len(ALL): break
        x = ALL[idx+k]
        hw = struct.unpack_from("<H", data, off(x.address))[0]
        note = ""
        # 该地址是否是 32 位指令起点而我们按 32 位解出了不同结果
        ins32 = force32(x.address)
        if ins32 and ins32.size == 4 and x.size == 2:
            note = "  <== 32位! => %s %s" % (ins32.mnemonic, ins32.op_str)
        print("     %08X  %-8s %-22s%s" % (x.address, x.mnemonic, x.op_str, note))

print()
print("=" * 82)
print("[B] 每条 movt #0x4000 之后 20 条内的 访存/常量，标注 I2C 寄存器语义")
for s in sites:
    idx = ALL.index(s)
    win = ALL[idx:idx+40]
    has4000 = any(x.mnemonic=="movt" and len(x.operands)==2 and x.operands[1].type==ARM_OP_IMM
                  and x.operands[1].imm==0x4000 for x in win[:4])
    if not has4000: continue
    # 找到寄存器名
    base = s.reg_name(s.operands[0].reg)
    print("\n  --- I2C1 基址在 %s  @ %08X ---" % (base, s.address))
    for x in win:
        txt = None
        if x.mnemonic in ("ldr","ldrb","ldrh","str","strb","strh") and x.operands \
           and x.operands[0].type == ARM_OP_MEM and x.operands[0].mem.base:
            m = x.operands[0].mem
            if x.reg_name(m.base) == base and not m.index:
                d = m.disp
                reg = I2CREG.get(d, "I2C+0x%X" % d)
                txt = "%s %s" % ("READ " if x.mnemonic.startswith("ldr") else "WRITE", reg)
                if x.mnemonic.startswith("str") and len(x.operands)>1 and x.operands[1].type==ARM_OP_IMM:
                    v = x.operands[1].imm & 0xFFFFFFFF
                    bits = [n for b,n in CR1BIT.items() if v & b]
                    txt += "  value=0x%X %s" % (v, bits if d==0 else "")
        if txt: print("     %08X  %-8s %-24s %s" % (x.address, x.mnemonic, x.op_str, txt))
