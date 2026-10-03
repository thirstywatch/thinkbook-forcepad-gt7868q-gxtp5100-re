"""verify-B/i2cmap2.py — 修正版：正确的 mem 操作数位置
同一条指令里 mem 可能出现在 operand[0](ldr) 或 operand[1](str)。
"""
import struct, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO
def rd32(a):
    o = off(a)
    return struct.unpack_from("<I", data, o)[0] if 0 <= o <= len(data)-4 else None

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
ALL = []
a = A_LO
while a <= A_HI:
    ok = False
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; ok = True; break
    if not ok: a += 2

I2CREG = {0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",
          0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}
CR1BIT = {0x0001:"PE",0x0004:"SMBTYPE",0x0008:"ENARP",0x0010:"ENPEC",0x0020:"ENGC",
          0x0040:"NOSTRETCH",0x0080:"START",0x0100:"STOP",0x0200:"ACK",0x0400:"POS",
          0x0800:"PEC",0x1000:"ALERT",0x2000:"SWRST"}

def memop(ins):
    """返回 (mem, is_write) —— 兼容 mem 在 op0 或 op1 两种编码"""
    if not ins.operands: return None, None
    if ins.operands[0].type == ARM_OP_MEM:
        return ins.operands[0].mem, ins.mnemonic.startswith("str")
    if len(ins.operands) >= 2 and ins.operands[1].type == ARM_OP_MEM:
        return ins.operands[1].mem, ins.mnemonic.startswith("str")
    return None, None

def imm_of(ins, memidx):
    """若另一操作数是立即数则返回它"""
    for k, op in enumerate(ins.operands):
        if op.type == ARM_OP_IMM:
            return op.imm & 0xFFFFFFFF
    return None

regs = {}
def tgt(bn, disp):
    return ((regs[bn] + disp) & 0xFFFFFFFF) if bn in regs else None

hits = []
for ins in ALL:
    if ins.mnemonic in ("mov","movs","movw","movt") and len(ins.operands)==2 \
       and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_IMM:
        r=ins.reg_name(ins.operands[0].reg); v=ins.operands[1].imm & 0xFFFFFFFF
        if ins.mnemonic=="movw": regs[r]=((regs.get(r,0)&0xFFFF0000)|(v&0xFFFF))&0xFFFFFFFF
        elif ins.mnemonic=="movt": regs[r]=((regs.get(r,0)&0xFFFF)|((v&0xFFFF)<<16))&0xFFFFFFFF
        else: regs[r]=v
    elif ins.mnemonic=="mov" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_REG:
        s=ins.reg_name(ins.operands[1].reg); d0=ins.reg_name(ins.operands[0].reg)
        if s in regs: regs[d0]=regs[s]
    elif ins.mnemonic in ("add","adds","add.w") and len(ins.operands)==3 \
       and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_REG:
        d0=ins.reg_name(ins.operands[0].reg); a1=ins.reg_name(ins.operands[1].reg)
        o2=ins.operands[2]
        dv = (o2.imm if o2.type==ARM_OP_IMM else (regs.get(ins.reg_name(o2.reg)) if o2.type==ARM_OP_REG else None))
        if a1 in regs and dv is not None: regs[d0]=(regs[a1]+dv)&0xFFFFFFFF
    elif ins.mnemonic=="ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_MEM:
        m=ins.operands[1].mem
        if m.base and ins.reg_name(m.base)=="pc":
            v=rd32(((ins.address+4)&~3)+m.disp)
            if v is not None: regs[ins.reg_name(ins.operands[0].reg)]=v
    m, isw = memop(ins)
    if m is not None and m.base and not m.index:
        bn = ins.reg_name(m.base)
        t = tgt(bn, m.disp)
        if t is not None and 0x40005000 <= t <= 0x400057FF:
            hits.append((ins.address, ins.mnemonic, ins.op_str, t, isw, imm_of(ins, None)))

print("=" * 86)
print("[1] 所有访存目标落在 I2C1 空间 0x40005000-0x400057FF 的指令（常量传播，bl 保守清空）")
for pc, mn, ops, t, isw, imm in sorted(hits):
    d = t - 0x40005400
    rn = I2CREG.get(d, "base+0x%X" % d)
    extra = ""
    if d == 0 and isw and imm is not None:
        bits = [n for b, n in CR1BIT.items() if imm & b]
        extra = "  value=0x%X %s" % (imm, bits)
    print("  %08X  %-7s %-30s -> 0x%08X %-6s %s%s" %
          (pc, mn, ops, t, rn, "WRITE" if isw else "READ", extra))
print("  共 %d 条" % len(hits))

print()
print("=" * 86)
print("[2] 按寄存器偏移归类")
by = collections.defaultdict(list)
for pc, mn, ops, t, isw, imm in hits:
    by[t - 0x40005400].append((pc, mn, ops, isw, imm))
for d in sorted(by):
    lst = by[d]
    print("  +0x%02X %-6s x%d  reads=%d writes=%d" %
          (d, I2CREG.get(d, "?"), len(lst),
           sum(1 for x in lst if not x[3]), sum(1 for x in lst if x[3])))
    for pc, mn, ops, isw, imm in sorted(lst):
        print("        %08X %s %s %s" % (pc, mn, ops, ("val=0x%X" % imm) if imm is not None else ""))

print()
print("=" * 86)
print("[3] 全镜像 4 字节立即数落在 0x40005000-0x400057FF 的位置（DMA CPAR / 数据表候选）")
for o in range(0, len(data) - 3):
    v = struct.unpack_from("<I", data, o)[0]
    if 0x40005000 <= v <= 0x400057FF:
        print("  file f%05X -> %08X = 0x%08X" % (o, o - F_LO + A_LO, v))
