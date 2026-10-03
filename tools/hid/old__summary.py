"""verify-B/summary.py — 全局汇总（替代大输出计划）
(a) 所有 GPIO 端口(0x40010800-0x40012BFF)的访存，按 端口/寄存器偏移 聚类
(b) 检测 bit-bang 特征：同一函数内对同一端口的 BSRR 置位/复位成对出现
(c) I2C1 完整访存清单（含 RMW 值与 位语义）
(d) 其它总线 SPI1/SPI2/USART1-3/DMA1/DMA2 的配置+发送路径
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

# ------- 完整的常量传播（不因 bl 清空，改为标记不确定；这里用"最近一次物化"） -------
regs = {}
def memop(ins):
    if ins.operands and ins.operands[0].type == ARM_OP_MEM:
        return ins.operands[0].mem
    if len(ins.operands) >= 2 and ins.operands[1].type == ARM_OP_MEM:
        return ins.operands[1].mem
    return None
def imm(ins):
    for op in ins.operands:
        if op.type == ARM_OP_IMM: return op.imm & 0xFFFFFFFF
    return None

acc = []   # (pc, mnem, opstr, target, iswrite, immval, base, disp)
for ins in ALL:
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
    m = memop(ins)
    if m is not None and m.base and not m.index:
        bn = ins.reg_name(m.base)
        if bn in regs:
            acc.append((ins.address, ins.mnemonic, ins.op_str, (regs[bn]+m.disp)&0xFFFFFFFF,
                        ins.mnemonic.startswith("str"), imm(ins), bn, m.disp))

GPIO = {0x40010800:"GPIOA",0x40010C00:"GPIOB",0x40011000:"GPIOC",
        0x40011400:"GPIOD",0x40011800:"GPIOE",0x40011C00:"GPIOF",0x40012000:"GPIOG"}
GREG = {0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}
I2CREG = {0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",
          0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}

print("=" * 88)
print("[A] GPIO 端口访存聚类（只列 base+0x00..0x18 的合法寄存器偏移）")
g = collections.defaultdict(list)
for pc, mn, ops, t, isw, v, bn, d in acc:
    for base, name in GPIO.items():
        if base <= t <= base + 0x18 and (t - base) in GREG:
            g[(name, t - base)].append((pc, mn, isw, v))
            break
for k in sorted(g, key=lambda x: (x[0], x[1])):
    lst = g[k]
    print("  %-6s %-5s x%-3d 写=%-3d 读=%-3d  %s" %
          (k[0], GREG[k[1]], len(lst), sum(1 for x in lst if x[2]), sum(1 for x in lst if not x[2]),
           " ".join("%08X" % x[0] for x in lst[:10])))
print()
print("  [A2] 所有 GPIOx_BSRR / BRR / ODR 的写入明细（bit-bang 判别核心）")
for k in sorted(g, key=lambda x: (x[0], x[1])):
    if GREG[k[1]] in ("BSRR", "BRR", "ODR"):
        for pc, mn, isw, v in sorted(g[k]):
            if isw:
                print("    %08X %-7s %s %-6s=%s" % (pc, mn, "WRITE", GREG[k[1]],
                      ("0x%08X" % v) if v is not None else "(寄存器值)"))

print()
print("=" * 88)
print("[B] I2C1 空间访存（仅合法寄存器偏移 0x00-0x20）")
i = collections.defaultdict(list)
for pc, mn, ops, t, isw, v, bn, d in acc:
    if 0x40005400 <= t <= 0x40005420:
        i[(t-0x40005400)].append((pc, mn, ops, isw, v))
for d in sorted(i):
    print("  +0x%02X %-6s x%d" % (d, I2CREG.get(d,"?"), len(i[d])))
    for pc, mn, ops, isw, v in sorted(i[d]):
        print("      %08X %-7s %-26s %s%s" % (pc, mn, ops, "WRITE" if isw else "READ",
              (" val=0x%X" % v) if (isw and v is not None) else ""))

print()
print("=" * 88)
print("[C] 其它总线基址的物化点统计")
BUS = {0x40013000:"SPI1",0x40003800:"SPI2",0x40003C00:"SPI3",
       0x40013800:"USART1",0x40004400:"USART2",0x40004800:"USART3",
       0x40020000:"DMA1",0x40020400:"DMA2",0x40021000:"RCC",0x40010000:"AFIO"}
nb = collections.Counter()
for pc, mn, ops, t, isw, v, bn, d in acc:
    for base, name in BUS.items():
        if base <= t < base + 0x400:
            nb[(name, isw)] += 1
            break
for k in sorted(nb):
    print("  %-7s %s x%d" % (k[0], "WRITE" if k[1] else "READ ", nb[k]))
