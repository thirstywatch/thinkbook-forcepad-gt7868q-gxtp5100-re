"""verify-B/finalverify.py — 最终裁决用
(A) I2C1 全部访存（含 mov 传递 / 间接），以计数
(B) GPIOC/GPIOx BSRR/BRR/ODR 写入：区分"库函数体内(参数化)" vs "实际调用点"
(C) CR1 写入位分析
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

def materializations():
    reg = {}; out = []
    for ins in ALL:
        if ins.mnemonic in ("mov","movs","movw","movt") and len(ins.operands)==2 \
           and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_IMM:
            r=ins.reg_name(ins.operands[0].reg); v=ins.operands[1].imm & 0xFFFFFFFF
            if ins.mnemonic=="movw": reg[r]=((reg.get(r,0)&0xFFFF0000)|(v&0xFFFF))&0xFFFFFFFF
            elif ins.mnemonic=="movt": reg[r]=((reg.get(r,0)&0xFFFF)|((v&0xFFFF)<<16))&0xFFFFFFFF
            else: reg[r]=v
            out.append((ins.address, r, reg[r]))
        elif ins.mnemonic=="ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
           and ins.operands[1].type==ARM_OP_MEM and ins.operands[1].mem.base \
           and ins.reg_name(ins.operands[1].mem.base)=="pc":
            v=rd32(((ins.address+4)&~3)+ins.operands[1].mem.disp)
            if v is not None:
                reg[ins.reg_name(ins.operands[0].reg)]=v
                out.append((ins.address, ins.reg_name(ins.operands[0].reg), v))
    return out
MATS = materializations()

def sweep(full_target, disp_range, window=250):
    """对每个精确物化点，跟踪并返回该窗口内落到 [full+lo, full+hi) 的访存"""
    res = []
    for at, r, full in MATS:
        if full != full_target: continue
        holds = {r}; k = IDX[at]; c = 0
        while k < len(ALL) and c < window:
            ins = ALL[k]
            if ins.mnemonic in ("mov","mov.w") and len(ins.operands)==2 and \
               all(o.type==ARM_OP_REG for o in ins.operands):
                s=ins.reg_name(ins.operands[1].reg); d=ins.reg_name(ins.operands[0].reg)
                if s in holds: holds.add(d)
            m=None
            if ins.operands and ins.operands[0].type==ARM_OP_MEM: m=ins.operands[0].mem
            elif len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_MEM: m=ins.operands[1].mem
            if m is not None and m.base and not m.index and ins.reg_name(m.base) in holds:
                t = full + m.disp
                if disp_range[0] <= m.disp < disp_range[1]:
                    v=None
                    for op in ins.operands:
                        if op.type==ARM_OP_IMM: v=op.imm & 0xFFFFFFFF
                    res.append((ins.address, ins.mnemonic, ins.op_str, m.disp,
                                ins.mnemonic.startswith("str"), v, at))
            if ins.mnemonic=="pop" and "pc" in ins.op_str: break
            if ins.mnemonic=="bx" and ins.op_str.strip()=="lr": break
            k+=1; c+=1
    return res

print("="*96)
print("[A] I2C1 (0x40005400) 全部访存 —— 每个物化点独立扫描")
r = sweep(0x40005400, (0, 0x40))
I2CREG={0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}
seen=set()
for pc, mn, ops, d, isw, v, at in sorted(r):
    if (pc,mn,ops) in seen: continue
    seen.add((pc,mn,ops))
    print("   %08X %-8s %-28s I2C1.%-6s %s %s   [物化点 %08X]" %
          (pc, mn, ops, I2CREG.get(d,"+0x%X"%d), "WRITE" if isw else "READ ",
           ("val=0x%X"%v) if v is not None else "", at))
print("   合计 %d 条" % len(seen))
w = [x for x in seen if x[0] in (0x08008A6C,)]
print("   其中 CR1 写: %s" % (" ".join("%08X"%x[0] for x in seen if x[0]==0x08008A6C) or "(无)"))

print()
print("="*96)
print("[B] GPIOC/GPIOB 基址物化点所在函数 vs BSRR/BRR/ODR 写位置（判断是否参数化库函数）")
for tgt, nm in [(0x40011000,"GPIOC"),(0x40010C00,"GPIOB"),(0x40010800,"GPIOA")]:
    r = sweep(tgt, (0x00, 0x1C))
    writes = collections.Counter()
    for pc, mn, ops, d, isw, v, at in r:
        if isw and d in (0x0C,0x10,0x14,0x18):
            writes[at] += 1
    print("   %s: 物化点->写次数 %s" % (nm, dict(writes) or "(无)"))

print()
print("="*96)
print("[C] 0x08008A4C 函数体（唯一 CR1 写）")
lo, hi = 0x08008A4C, 0x08008A70
for ins in ALL:
    if lo <= ins.address <= hi:
        print("   %08X  %-9s %s" % (ins.address, ins.mnemonic, ins.op_str))

print()
print("="*96)
print("[D] GPIO 位操作库函数入口确认（是否有非参数化的直接 GPIO 常量写）")
funcs = {0x08010D1C:"GPIO_ResetBits?",0x08010D30:"GPIO_SetBits?",0x08010D44:"GPIO_ReadOutputDataBit?",
         0x08010D80:"?",0x08010DB0:"?"}
for f, nm in funcs.items():
    txt = " ".join("%s %s" % (i.mnemonic, i.op_str) for i in ALL[IDX[f]:IDX[f]+10])
    print("   %08X %-26s %s" % (f, nm, txt))
