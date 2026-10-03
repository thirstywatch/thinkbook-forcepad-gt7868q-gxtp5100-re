"""verify-B/final_q.py — 收尾确定性检查
(1) DMA1/DMA2 通道配置点及其 CPAR/CMAR 赋值
(2) 全镜像 GPIO BSRR/BRR/ODR 写入（含 movt 隐式物化，修 census 的 movw 缺失 bug）
(3) I2C1 的 DMA 关联（CPAR==0x40005400/0x40005410）
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

# 物化：movt 单独也能给高半（低半视为 0 或之前的值）
mats = []
reg = {}
for ins in ALL:
    if ins.mnemonic in ("mov","movs","movw","movt") and len(ins.operands)==2 \
       and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_IMM:
        r=ins.reg_name(ins.operands[0].reg); v=ins.operands[1].imm & 0xFFFFFFFF
        if ins.mnemonic=="movw": reg[r]=((reg.get(r,0)&0xFFFF0000)|(v&0xFFFF))&0xFFFFFFFF
        elif ins.mnemonic=="movt": reg[r]=((reg.get(r,0)&0xFFFF)|((v&0xFFFF)<<16))&0xFFFFFFFF
        else: reg[r]=v
        mats.append((ins.address, r, reg[r]))
    elif ins.mnemonic=="ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_MEM and ins.operands[1].mem.base \
       and ins.reg_name(ins.operands[1].mem.base)=="pc":
        v=rd32(((ins.address+4)&~3)+ins.operands[1].mem.disp)
        if v is not None:
            reg[ins.reg_name(ins.operands[0].reg)]=v
            mats.append((ins.address, ins.reg_name(ins.operands[0].reg), v))

GPIO = {0x40010800:"GPIOA",0x40010C00:"GPIOB",0x40011000:"GPIOC",
        0x40011400:"GPIOD",0x40011800:"GPIOE"}
GR = {0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}

print("="*94)
print("[1] 所有 GPIO BSRR / BRR / ODR 写入（bit-bang 判定核心）")
n = 0
for at, r, full in mats:
    base = None
    for b, nm in GPIO.items():
        if full == b: base=b; name=nm; break
    if base is None: continue
    holds={r}; k=IDX[at]; c=0
    while k < len(ALL) and c < 200:
        ins=ALL[k]
        if ins.mnemonic in ("mov","mov.w") and len(ins.operands)==2 and \
           all(o.type==ARM_OP_REG for o in ins.operands):
            s=ins.reg_name(ins.operands[1].reg); d=ins.reg_name(ins.operands[0].reg)
            if s in holds: holds.add(d)
        m=None
        if ins.operands and ins.operands[0].type==ARM_OP_MEM: m=ins.operands[0].mem
        elif len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_MEM: m=ins.operands[1].mem
        if m is not None and m.base and not m.index and ins.reg_name(m.base) in holds \
           and ins.mnemonic.startswith("str") and m.disp in (0x0C,0x10,0x14,0x18):
            v=None
            for op in ins.operands:
                if op.type==ARM_OP_IMM: v=op.imm & 0xFFFFFFFF
            print("   %08X %-8s %-28s %s.%s %s" % (ins.address, ins.mnemonic, ins.op_str,
                  name, GR[m.disp], ("val=0x%X"%v) if v is not None else "(寄存器值)"))
            n+=1
        if ins.mnemonic=="pop" and "pc" in ins.op_str: break
        k+=1; c+=1
if n==0: print("   >>> 零命中：全镜像没有任何 GPIO BSRR/BRR/ODR 写入 <<<")

print()
print("="*94)
print("[2] DMA1/DMA2 通道配置点（CPAR/CMAR/CCR 写入）")
DMAREG={0:"CCR",4:"CNDTR",8:"CPAR",0x0C:"CMAR"}
cnt=0
for at, r, full in mats:
    if full not in (0x40020000,0x40020400): continue
    nm = "DMA1" if full==0x40020000 else "DMA2"
    holds={r}; k=IDX[at]; c=0
    while k < len(ALL) and c < 300:
        ins=ALL[k]
        if ins.mnemonic in ("mov","mov.w") and len(ins.operands)==2 and \
           all(o.type==ARM_OP_REG for o in ins.operands):
            s=ins.reg_name(ins.operands[1].reg); d=ins.reg_name(ins.operands[0].reg)
            if s in holds: holds.add(d)
        m=None
        if ins.operands and ins.operands[0].type==ARM_OP_MEM: m=ins.operands[0].mem
        elif len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_MEM: m=ins.operands[1].mem
        if m is not None and m.base and not m.index and ins.reg_name(m.base) in holds \
           and 0 <= m.disp < 0x200:
            ch=m.disp//0x14; io=m.disp%0x14
            rn=DMAREG.get(io,"+0x%X"%m.disp)
            t=(full+m.disp)
            star = "  <<< 指向 I2C1!" if 0x40005400 <= t <= 0x40005440 else ""
            print("   %08X %-8s %-28s %s ch%d %s%s" % (ins.address, ins.mnemonic, ins.op_str,
                  nm, ch+1, rn, star))
            cnt+=1
        if ins.mnemonic=="pop" and "pc" in ins.op_str: break
        k+=1; c+=1
if cnt==0: print("   (无)")

print()
print("="*94)
print("[3] 全镜像 4 字节 LE 值落在 DMA CPAR 会用到的任何外设区，且靠近 DMA 初始化代码")
for o in range(0, len(data)-3):
    v = struct.unpack_from("<I", data, o)[0]
    if 0x40000000 <= v <= 0x4003FFFF:
        a2 = o - F_LO + A_LO
        if 0x08005000 <= a2 <= 0x08012342:
            print("   f%05X -> %08X = 0x%08X" % (o, a2, v))
