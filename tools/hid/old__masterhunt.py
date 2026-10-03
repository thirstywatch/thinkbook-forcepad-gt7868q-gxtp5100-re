"""verify-B/masterhunt.py — 决定性：找 I2C1 控制类寄存器的写入，含间接/计算寻址
策略：把整段代码按"函数"切分（push 入口），对每个函数做前向寄存器常量跟踪，
遇到目标落在 0x40005400..0x4000543F 的写操作就报告；同时对 CR1/CR2/CCR/TRISE
搜索 START/STOP/SWRST/PE/DMAEN/ITBUFEN 等位。
"""
import struct, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO
def rd32(a):
    o = off(a); return struct.unpack_from("<I", data, o)[0] if 0 <= o <= len(data)-4 else None
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
ALL = []
a = A_LO
while a <= A_HI:
    ok=False
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; ok=True; break
    if not ok: a += 2
IDX = {ins.address: k for k, ins in enumerate(ALL)}

# 函数切分：push 入口 或 向量表目标
VEC = [0x08005165,0x0800A679,0x08008895,0x0800A449,0x080053F5,0x0800DFE5,
       0x0800BE25,0x080053F9,0x0800B75D,0x0800CE7D,0x08006B3D,0x0800D629,
       0x08008979,0x0800894D,0x0800DEE9]
VEC = [v & ~1 for v in VEC]
ENTRIES = sorted(set([ins.address for ins in ALL if ins.mnemonic == "push"] + VEC))

# --- 1) 逐函数常量跟踪，找对 I2C1 CR1/CR2/CCR/TRISE/OAR 的写 ---
I2C_LO, I2C_HI = 0x40005400, 0x4000543F
CTRL = {0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x1C:"CCR",0x20:"TRISE"}
CR1_BITS = {"PE":1,"SMBUS":2,"SMBTYPE":4,"ENARP":8,"ENPEC":0x10,"ENGC":0x20,
            "NOSTRETCH":0x40,"START":0x80,"STOP":0x100,"ACK":0x200,"POS":0x400,
            "PEC":0x800,"ALERT":0x1000,"SWRST":0x2000}
CR2_BITS = {"FREQ":0x3F,"ITERREN":0x100,"ITBUFEN":0x200,"ITevent":0x400,"DMAEN":0x800,"LAST":0x1000}

print("="*92)
print("[1] 所有写向 I2C1 寄存器块(0x40005400-0x4000543F)的 store（含 RMW 前的常量）")
for fi, ent in enumerate(ENTRIES):
    end = ENTRIES[fi+1] if fi+1 < len(ENTRIES) else A_HI+1
    regs = {}
    k = IDX.get(ent)
    if k is None: continue
    while k < len(ALL) and ALL[k].address < end:
        ins = ALL[k]
        if ins.mnemonic in ("mov","movs","movw","movt") and len(ins.operands)==2 \
           and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_IMM:
            r=ins.reg_name(ins.operands[0].reg); v=ins.operands[1].imm & 0xFFFFFFFF
            if ins.mnemonic=="movw": regs[r]=((regs.get(r,0)&0xFFFF0000)|(v&0xFFFF))&0xFFFFFFFF
            elif ins.mnemonic=="movt": regs[r]=((regs.get(r,0)&0xFFFF)|((v&0xFFFF)<<16))&0xFFFFFFFF
            else: regs[r]=v
        elif ins.mnemonic=="mov" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
           and ins.operands[1].type==ARM_OP_REG:
            s=ins.reg_name(ins.operands[1].reg); d=ins.reg_name(ins.operands[0].reg)
            if s in regs: regs[d]=regs[s]
        elif ins.mnemonic in ("add","adds","add.w") and len(ins.operands)==3 \
           and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_REG:
            d=ins.reg_name(ins.operands[0].reg); a1=ins.reg_name(ins.operands[1].reg)
            o2=ins.operands[2]
            dv=(o2.imm if o2.type==ARM_OP_IMM else (regs.get(ins.reg_name(o2.reg)) if o2.type==ARM_OP_REG else None))
            if a1 in regs and dv is not None: regs[d]=(regs[a1]+dv)&0xFFFFFFFF
        elif ins.mnemonic=="ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
           and ins.operands[1].type==ARM_OP_MEM:
            m=ins.operands[1].mem
            if m.base and ins.reg_name(m.base)=="pc":
                v=rd32(((ins.address+4)&~3)+m.disp)
                if v is not None: regs[ins.reg_name(ins.operands[0].reg)]=v
        # 或/与 立即数 -> 也能物化
        elif ins.mnemonic in ("orr","orrs","bic","ands") and len(ins.operands)==3 \
           and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_REG \
           and ins.operands[2].type==ARM_OP_IMM:
            d=ins.reg_name(ins.operands[0].reg); s=ins.reg_name(ins.operands[1].reg)
            if s in regs:
                v=ins.operands[2].imm
                regs[d] = (regs[s] | v) if ins.mnemonic.startswith("orr") else (regs[s] & ~v)
        # store
        if ins.mnemonic.startswith("str"):
            mm = None
            if ins.operands and ins.operands[0].type == ARM_OP_MEM: mm = ins.operands[0].mem
            elif len(ins.operands)>=2 and ins.operands[1].type == ARM_OP_MEM: mm = ins.operands[1].mem
            if mm is not None and mm.base and not mm.index:
                bn = ins.reg_name(mm.base)
                if bn in regs:
                    t = (regs[bn] + mm.disp) & 0xFFFFFFFF
                    if I2C_LO <= t <= I2C_HI:
                        d = t - I2C_LO
                        val = None
                        for op in ins.operands:
                            if op.type == ARM_OP_IMM: val = op.imm & 0xFFFFFFFF
                            elif op.type == ARM_OP_REG:
                                rn = ins.reg_name(op.reg)
                                if rn in regs: val = regs[rn]
                        print("  %08X (fn %08X) %-8s %-26s -> I2C1 %s  值=%s" %
                              (ins.address, ent, ins.mnemonic, ins.op_str,
                               CTRL.get(d, "+0x%X" % d), ("0x%X" % val) if val is not None else "?"))
        k += 1

print()
print("="*92)
print("[2] 全镜像对 CR1(0x40005400) 的位操作值统计（从 imm 直接看 START/STOP）")
for ins in ALL:
    for op in ins.operands:
        if op.type == ARM_OP_IMM and op.imm in (0x80, 0x100, 0x200, 0x400, 0x2000, 0x800):
            if ins.mnemonic in ("orr","orrs","bic","ands","str","tst","and","cmp"):
                print("  %08X %-8s %-28s imm=0x%X" % (ins.address, ins.mnemonic, ins.op_str, op.imm))
            break
