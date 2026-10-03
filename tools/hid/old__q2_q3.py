"""verify-B/q2_q3.py — Q2(第二 I2C) / Q3(SPI/USART/DMA 发送路径) 确定性检查"""
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

print("="*94)
print("[Q2] 是否存在第二/第三 I2C 外设 (0x40005800 / 0x40005C00 / 0x40006000)")
for target, nm in [(0x40005800,"I2C2"),(0x40005C00,"?"),(0x40006000,"?"),(0x40006400,"?"),(0x40006800,"?")]:
    hits = []
    for ins in ALL:
        for op in ins.operands:
            if op.type == ARM_OP_IMM and (op.imm & 0xFFFFFFFF) == target:
                hits.append((ins.address, ins.mnemonic, ins.op_str))
            if op.type == ARM_OP_MEM and op.mem.base and ins.reg_name(op.mem.base)=="pc":
                if rd32(((ins.address+4)&~3)+op.mem.disp) == target:
                    hits.append((ins.address, "ldr-pool", ins.op_str))
    print("  0x%08X %-5s 直接常量命中 %d : %s" % (target, nm, len(hits),
          "; ".join("%08X %s %s" % h for h in hits[:6])))
# movw #0x5800 / 0x5C00 / 0x6000 配对
print()
print("  movw/movt 配对还原值落在 0x40005000-0x40006FFF（I2C 区）的全部：")
lastw = {}
for ins in ALL:
    if ins.mnemonic=="movw" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        lastw[ins.reg_name(ins.operands[0].reg)] = (ins.address, ins.operands[1].imm & 0xFFFF)
    elif ins.mnemonic=="movt" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        r=ins.reg_name(ins.operands[0].reg)
        lo = lastw.pop(r)[1] if r in lastw else 0
        full = (lo | ((ins.operands[1].imm & 0xFFFF)<<16)) & 0xFFFFFFFF
        if 0x40005000 <= full <= 0x40006FFF:
            print("     %08X -> 0x%08X" % (ins.address, full))

print()
print("="*94)
print("[Q3a] SPI 外设基址物化及 DR 写入")
spis = []
lastw = {}
for ins in ALL:
    if ins.mnemonic=="movw" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        lastw[ins.reg_name(ins.operands[0].reg)] = (ins.address, ins.operands[1].imm & 0xFFFF)
    elif ins.mnemonic=="movt" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        r=ins.reg_name(ins.operands[0].reg)
        lo = lastw.pop(r)[1] if r in lastw else 0
        full = (lo | ((ins.operands[1].imm & 0xFFFF)<<16)) & 0xFFFFFFFF
        if full in (0x40013000,0x40003800,0x40003C00):
            spis.append((ins.address, r, full))
print("  SPI 基址物化点: %s" % ("; ".join("%08X %s 0x%08X" % s for s in spis) or "(无)"))
for at, r, full in spis:
    holds = {r}; k = IDX[at]; n=0
    while k < len(ALL) and n < 400:
        ins = ALL[k]
        if ins.mnemonic in ("mov","mov.w") and len(ins.operands)==2 and \
           all(o.type==ARM_OP_REG for o in ins.operands):
            s=ins.reg_name(ins.operands[1].reg); d=ins.reg_name(ins.operands[0].reg)
            if s in holds: holds.add(d)
        m = None
        if ins.operands and ins.operands[0].type==ARM_OP_MEM: m=ins.operands[0].mem
        elif len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_MEM: m=ins.operands[1].mem
        if m is not None and m.base and not m.index and ins.reg_name(m.base) in holds \
           and full <= (full+m.disp) < full+0x40:
            print("     %08X %-8s %-26s +0x%X %s" % (ins.address, ins.mnemonic, ins.op_str,
                  m.disp, "WRITE" if ins.mnemonic.startswith("str") else "READ"))
        if ins.mnemonic=="pop" and "pc" in ins.op_str: break
        k+=1; n+=1

print()
print("="*94)
print("[Q3b] DMA1/DMA2 寄存器写（通道 CCR/CNDTR/CPAR/CMAR）")
DMAREG = ["CCR","CNDTR","CPAR","CMAR"]
for base, nm in [(0x40020000,"DMA1"),(0x40020400,"DMA2")]:
    lastw = {}
    cnt = 0
    for k, ins in enumerate(ALL):
        if ins.mnemonic=="movw" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
            lastw[ins.reg_name(ins.operands[0].reg)] = (ins.address, ins.operands[1].imm & 0xFFFF)
        elif ins.mnemonic=="movt" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
            r=ins.reg_name(ins.operands[0].reg)
            lo = lastw.pop(r)[1] if r in lastw else 0
            full = (lo | ((ins.operands[1].imm & 0xFFFF)<<16)) & 0xFFFFFFFF
            if full == base:
                holds={r}; j=k; n=0
                while j < len(ALL) and n < 200:
                    x = ALL[j]
                    if x.mnemonic in ("mov","mov.w") and len(x.operands)==2 and \
                       all(o.type==ARM_OP_REG for o in x.operands):
                        s=x.reg_name(x.operands[1].reg); d=x.reg_name(x.operands[0].reg)
                        if s in holds: holds.add(d)
                    m=None
                    if x.operands and x.operands[0].type==ARM_OP_MEM: m=x.operands[0].mem
                    elif len(x.operands)>=2 and x.operands[1].type==ARM_OP_MEM: m=x.operands[1].mem
                    if m is not None and m.base and not m.index and x.reg_name(m.base) in holds:
                        if 0 <= m.disp < 0x500:
                            ch = m.disp // 0x14; off_in = m.disp % 0x14
                            rn = DMAREG[off_in//4] if off_in % 4 == 0 and off_in//4 < 4 else "?+0x%X" % m.disp
                            print("     %08X %-8s %-28s %s ch%d %s" % (x.address, x.mnemonic, x.op_str,
                                  nm, ch+1, rn))
                            cnt += 1
                    if x.mnemonic=="pop" and "pc" in x.op_str: break
                    j+=1; n+=1
    if cnt == 0: print("  %s: 无基址物化（未直接访问）" % nm)

print()
print("="*94)
print("[Q3c] USART DR 写入（发送字节）")
lastw = {}
for k, ins in enumerate(ALL):
    if ins.mnemonic=="movw" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        lastw[ins.reg_name(ins.operands[0].reg)] = (ins.address, ins.operands[1].imm & 0xFFFF)
    elif ins.mnemonic=="movt" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        r=ins.reg_name(ins.operands[0].reg)
        lo = lastw.pop(r)[1] if r in lastw else 0
        full = (lo | ((ins.operands[1].imm & 0xFFFF)<<16)) & 0xFFFFFFFF
        if full in (0x40013800,0x40004400,0x40004800,0x40004C00,0x40005000,0x40003800):
            holds={r}; j=k; n=0
            while j < len(ALL) and n < 120:
                x = ALL[j]
                if x.mnemonic in ("mov","mov.w") and len(x.operands)==2 and \
                   all(o.type==ARM_OP_REG for o in x.operands):
                    s=x.reg_name(x.operands[1].reg); d=x.reg_name(x.operands[0].reg)
                    if s in holds: holds.add(d)
                m=None
                if x.operands and x.operands[0].type==ARM_OP_MEM: m=x.operands[0].mem
                elif len(x.operands)>=2 and x.operands[1].type==ARM_OP_MEM: m=x.operands[1].mem
                if m is not None and m.base and not m.index and x.reg_name(m.base) in holds \
                   and 0 <= m.disp < 0x40:
                    print("     %08X %-8s %-28s base=0x%08X +0x%X %s" % (x.address, x.mnemonic,
                          x.op_str, full, m.disp, "WRITE" if x.mnemonic.startswith("str") else "READ"))
                if x.mnemonic=="pop" and "pc" in x.op_str: break
                j+=1; n+=1
