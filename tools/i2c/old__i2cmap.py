"""verify-B/i2cmap.py — 权威：全镜像里所有可能落在 I2C1(0x40005400) 空间的访存
方法：
  path1) movw/movt 配对物化 0x400054xx，随后用该寄存器做 [r,disp]
  path2) 全局线性常量传播：跟踪每个寄存器的最新 32 位常量，报告 [reg+disp] 命中
  path3) DMA 通道 CPAR 是否被写成 0x400054xx
"""
import struct, collections, re
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO
def rd32(a):
    o = off(a)
    if o < 0 or o + 4 > len(data): return None
    return struct.unpack_from("<I", data, o)[0]

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
ALL = []
a = A_LO
while a <= A_HI:
    ok = False
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; ok = True; break
    if not ok: a += 2
AT = {i.address: i for i in ALL}

I2C_SPACE = "I2C"
I2CREG = {0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",
          0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}
CR1BIT = {0x0001:"PE",0x0004:"SMBTYPE",0x0008:"ENARP",0x0010:"ENPEC",0x0020:"ENGC",
          0x0040:"NOSTRETCH",0x0080:"START",0x0100:"STOP",0x0200:"ACK",0x0400:"POS",
          0x0800:"PEC",0x1000:"ALERT",0x2000:"SWRST"}
SR1BIT = {0x0001:"SB",0x0002:"ADDR",0x0004:"BTF",0x0008:"ADD10",0x0010:"STOPF",
          0x0040:"RXNE",0x0080:"TXE",0x0100:"GENCALL",0x0200:"DUALF",0x0400:"PECERR",
          0x0800:"OVR",0x1000:"AF",0x2000:"ARLO",0x4000:"BERR"}
SR2BIT = {0x0001:"MSL",0x0002:"BUSY",0x0004:"TRA",0x0008:"RD_WRN"}

# ---------- 路径 1/2：常量传播 ----------
# 逐指令跟踪 16 个通用寄存器 + 记录 (addr, reg, value)
regs = {}
hits = []          # (pc, kind, reg, disp, resolved_addr, mnem, opstr)
def target_for(regname, disp):
    if regname in regs:
        return (regs[regname] + disp) & 0xFFFFFFFF
    return None

for ins in ALL:
    # 更新常量
    if ins.mnemonic in ("mov","movs","movw","movt") and len(ins.operands)==2 \
       and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg); v = ins.operands[1].imm & 0xFFFFFFFF
        if ins.mnemonic=="movw": regs[r]=((regs.get(r,0)&0xFFFF0000)|(v&0xFFFF))&0xFFFFFFFF
        elif ins.mnemonic=="movt": regs[r]=((regs.get(r,0)&0xFFFF)|((v&0xFFFF)<<16))&0xFFFFFFFF
        else: regs[r]=v
    elif ins.mnemonic in ("add","adds","add.w") and len(ins.operands)>=3 \
       and all(o.type==ARM_OP_REG for o in ins.operands[:3]):
        d=ins.reg_name(ins.operands[0].reg); a1=ins.reg_name(ins.operands[1].reg); a2=ins.reg_name(ins.operands[2].reg)
        if a1 in regs and a2 in regs: regs[d]=(regs[a1]+regs[a2])&0xFFFFFFFF
    elif ins.mnemonic in ("add","adds") and len(ins.operands)==3 \
       and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_REG \
       and ins.operands[2].type==ARM_OP_IMM:
        d=ins.reg_name(ins.operands[0].reg); a1=ins.reg_name(ins.operands[1].reg)
        if a1 in regs: regs[d]=(regs[a1]+ins.operands[2].imm)&0xFFFFFFFF
    elif ins.mnemonic=="mov" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_REG:
        s=ins.reg_name(ins.operands[1].reg); d=ins.reg_name(ins.operands[0].reg)
        if s in regs: regs[d]=regs[s]
    elif ins.mnemonic=="ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_MEM:
        m=ins.operands[1].mem
        if m.base and ins.reg_name(m.base)=="pc":
            va=((ins.address+4)&~3)+m.disp; v=rd32(va)
            if v is not None: regs[ins.reg_name(ins.operands[0].reg)]=v
    # 检查访存
    if ins.operands and ins.operands[0].type==ARM_OP_MEM:
        m=ins.operands[0].mem
        if m.base:
            bn=ins.reg_name(m.base)
            t=target_for(bn, m.disp)
            if t is not None and 0x40005000 <= t <= 0x400057FF:
                hits.append((ins.address, ins.mnemonic, ins.op_str, t, bn, m.disp))
    # bl 会破坏寄存器常量：保守清空被调函数可能改的寄存器 -> 全部清空
    if ins.mnemonic in ("bl","blx"):
        regs = {k:v for k,v in regs.items() if k in ("r0",)}  # 极保守

print("=" * 84)
print("[1] 常量传播命中：访存目标落在 0x40005000-0x400057FF（I2C1 空间）")
seen=set()
for pc, mn, ops, t, bn, d in hits:
    key=(pc,mn,ops)
    if key in seen: continue
    seen.add(key)
    reg = I2CREG.get(t-0x40005400, "I2C1+0x%X" % (t-0x40005400))
    print("  %08X  %-8s %-28s -> 0x%08X (%s)  [base %s+0x%X]" % (pc, mn, ops, t, reg, bn, d))
print("  共 %d 条" % len(seen))

# ---------- 路径 3：所有对该空间的立即数写入（str rX,[reg] 形式，imm 在其它寄存器） ----------
print()
print("=" * 84)
print("[2] 所有在 I2C1 空间内出现过的偏移（按寄存器名）")
byoff = collections.defaultdict(list)
for pc, mn, ops, t, bn, d in hits:
    byoff[t-0x40005400].append((pc, mn, ops))
for d in sorted(byoff):
    print("  +0x%02X %-6s x%d" % (d, I2CREG.get(d,"?"), len(byoff[d])))

# ---------- 路径 4：DMA CPAR ----------
print()
print("=" * 84)
print("[3] DMA1/DMA2 通道寄存器块中出现 0x400054xx 的地方")
# DMA1 base 0x40020000, 每通道 0x14 字节；CPAR 是通道内 +0x10
for o in range(0, len(data)-3):
    v = struct.unpack_from("<I", data, o)[0]
    if 0x40005000 <= v <= 0x400057FF:
        a = o - F_LO + A_LO
        print("  file f%05X -> %08X = 0x%08X" % (o, a, v))
