"""verify-B/census.py — 全局外设访存普查（固定前视窗口法，不依赖函数边界猜测）
对每个"基址物化点"，向前扫描 N 条指令（或遇到函数返回），跟踪该基址寄存器的所有
副本，报告所有 [reg+disp] 读写。窗口足够大且不依赖 push 切分。
"""
import struct, collections, sys
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
WIN = int(sys.argv[1]) if len(sys.argv) > 1 else 80

REGIONS = {
 "I2C1":      (0x40005400, 0x40005440, {0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}),
 "GPIOA":     (0x40010800, 0x4001081C, {0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}),
 "GPIOB":     (0x40010C00, 0x40010C1C, {0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}),
 "GPIOC":     (0x40011000, 0x4001101C, {0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}),
 "SPI1":      (0x40013000, 0x40013024, {0x00:"CR1",0x04:"CR2",0x08:"SR",0x0C:"DR",0x10:"CRCPR",0x14:"RXCRCR",0x18:"TXCRCR",0x1C:"I2SCFGR",0x20:"I2SPR"}),
 "SPI2":      (0x40003800, 0x40003824, {0x00:"CR1",0x04:"CR2",0x08:"SR",0x0C:"DR",0x10:"CRCPR",0x14:"RXCRCR",0x18:"TXCRCR",0x1C:"I2SCFGR",0x20:"I2SPR"}),
 "USART1":    (0x40013800, 0x4001381C, {0x00:"SR",0x04:"DR",0x08:"BRR",0x0C:"CR1",0x10:"CR2",0x14:"CR3",0x18:"GTPR"}),
 "USART2":    (0x40004400, 0x4000441C, {0x00:"SR",0x04:"DR",0x08:"BRR",0x0C:"CR1",0x10:"CR2",0x14:"CR3"}),
 "USART3":    (0x40004800, 0x4000481C, {0x00:"SR",0x04:"DR",0x08:"BRR",0x0C:"CR1",0x10:"CR2",0x14:"CR3"}),
 "DMA1":      (0x40020000, 0x40020080, None),
 "DMA2":      (0x40020400, 0x40020480, None),
 "P_6C00":    (0x40006C00, 0x40006C20, None),
 "P_7000":    (0x40007000, 0x40007020, None),
 "P_1400":    (0x40001400, 0x40001420, None),
 "P_5C00":    (0x40005C00, 0x40005C40, {0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}),
 "P_6000":    (0x40006000, 0x40006040, {0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}),
}
def region_of(v):
    for nm, (lo, hi, mp) in REGIONS.items():
        if lo <= v < hi: return nm, mp
    return None, None

# 收集所有 (物化地址, 寄存器, 值)
mats = []
lastw = {}
for ins in ALL:
    if ins.mnemonic == "movw" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        lastw[ins.reg_name(ins.operands[0].reg)] = (ins.address, ins.operands[1].imm & 0xFFFF)
    elif ins.mnemonic == "movt" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg)
        lo = 0
        if r in lastw: _, lo = lastw.pop(r)
        mats.append((ins.address, r, (lo | ((ins.operands[1].imm & 0xFFFF)<<16)) & 0xFFFFFFFF))
for ins in ALL:
    if ins.mnemonic == "ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_MEM and ins.operands[1].mem.base \
       and ins.reg_name(ins.operands[1].mem.base)=="pc":
        v = rd32(((ins.address+4)&~3)+ins.operands[1].mem.disp)
        if v is not None: mats.append((ins.address, ins.reg_name(ins.operands[0].reg), v))

report = collections.defaultdict(list)
for at, r, full in mats:
    nm, mp = region_of(full)
    if nm is None or mp is None: continue
    lo, hi, _ = REGIONS[nm]
    if full != lo: continue
    holds = {r}
    k = IDX[at]; n = 0
    while k < len(ALL) and n < WIN:
        ins = ALL[k]
        if ins.mnemonic in ("mov","mov.w") and len(ins.operands)==2 \
           and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_REG:
            s=ins.reg_name(ins.operands[1].reg); d=ins.reg_name(ins.operands[0].reg)
            if s in holds: holds.add(d)
        m = None
        if ins.operands and ins.operands[0].type==ARM_OP_MEM: m = ins.operands[0].mem
        elif len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_MEM: m = ins.operands[1].mem
        if m is not None and m.base and not m.index and ins.reg_name(m.base) in holds:
            d = m.disp
            if 0 <= d < (hi - lo) and d in mp:
                v = None
                for op in ins.operands:
                    if op.type == ARM_OP_IMM: v = op.imm & 0xFFFFFFFF
                report[(nm, mp[d])].append((ins.address, ins.mnemonic, ins.op_str,
                                            ins.mnemonic.startswith("str"), v))
        if ins.mnemonic in ("pop","bx") and ("pc" in ins.op_str or ins.op_str.strip()=="lr"):
            break
        k += 1; n += 1

print("窗口=%d 指令" % WIN)
print("="*96)
for key in sorted(report):
    lst = sorted(set(report[key]))
    nm, reg = key
    print("\n  %s.%s  x%d  (写=%d 读=%d)" % (nm, reg, len(lst),
          sum(1 for x in lst if x[3]), sum(1 for x in lst if not x[3])))
    for pc, mn, ops, isw, v in lst:
        print("      %08X %-8s %-28s %s %s" % (pc, mn, ops, "WRITE" if isw else "READ ",
              ("val=0x%X" % v) if v is not None else ""))
