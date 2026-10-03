"""verify-B/full.py — 逐物化点 + 全函数窗口的确定性外设访问分析
对每个 movw/movt 配对得到的基址，跟踪该寄存器在整个函数内（到下一个 push 入口为止）
被用作 [r,disp] 的全部访存，以及被 mov 到其它寄存器后的访存。
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
ENTRIES = [ins.address for ins in ALL if ins.mnemonic == "push"]
def fn_end(a):
    for e in ENTRIES:
        if e > a: return e
    return A_HI + 1

MASKS = {
 0x40005400: ({0x00:"CR1",0x04:"CR2",0x08:"OAR1",0x0C:"OAR2",0x10:"DR",0x14:"SR1",0x18:"SR2",0x1C:"CCR",0x20:"TRISE"}, "I2C1"),
 0x40010800: ({0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}, "GPIOA"),
 0x40010C00: ({0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}, "GPIOB"),
 0x40011000: ({0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}, "GPIOC"),
 0x40011400: ({0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}, "GPIOD"),
 0x40013000: ({0x00:"CR1",0x04:"CR2",0x08:"SR",0x0C:"DR",0x10:"CRCPR",0x14:"RXCRCR",0x18:"TXCRCR",0x1C:"I2SCFGR",0x20:"I2SPR"}, "SPI1"),
 0x40003800: ({0x00:"CR1",0x04:"CR2",0x08:"SR",0x0C:"DR",0x10:"CRCPR"}, "SPI2"),
 0x40013800: ({0x00:"SR",0x04:"DR",0x08:"BRR",0x0C:"CR1",0x10:"CR2",0x14:"CR3",0x18:"GTPR"}, "USART1"),
 0x40004400: ({0x00:"SR",0x04:"DR",0x08:"BRR",0x0C:"CR1",0x10:"CR2",0x14:"CR3"}, "USART2"),
 0x40004800: ({0x00:"SR",0x04:"DR",0x08:"BRR",0x0C:"CR1",0x10:"CR2",0x14:"CR3"}, "USART3"),
 0x40020000: (None, "DMA1"),
 0x40020400: (None, "DMA2"),
 0x40006C00: (None, "0x40006C00"),
 0x40007000: (None, "0x40007000"),
}

# 1) 收集 movw/movt 配对
pairs = []
lastw = {}
for k, ins in enumerate(ALL):
    if ins.mnemonic == "movw" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        lastw[ins.reg_name(ins.operands[0].reg)] = (ins.address, ins.operands[1].imm & 0xFFFF)
    elif ins.mnemonic == "movt" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg)
        if r in lastw:
            wa, lo = lastw.pop(r)
            pairs.append((wa, ins.address, ins.address, r, (lo | ((ins.operands[1].imm & 0xFFFF) << 16)) & 0xFFFFFFFF))
        else:
            pairs.append((None, ins.address, ins.address, r, ((ins.operands[1].imm & 0xFFFF) << 16) & 0xFFFFFFFF))

print("=" * 92)
print("[A] 每个外设基址物化点所在函数的全部 [base+disp] 访存")
seen_fn = set()
for wa, mta, at, r, full in sorted(pairs, key=lambda x: x[2]):
    base = None; name = None
    for b, (mp, nm) in MASKS.items():
        if b <= full < b + 0x400:
            base = b; name = nm; break
    if base is None: continue
    if full != base:   # 只处理基址精确物化
        continue
    end = fn_end(at)
    key = (full, at)
    if key in seen_fn: continue
    seen_fn.add(key)
    # 从物化点向后扫到函数结束，跟踪 base 寄存器（含 mov 拷贝）
    holds = {r}
    rows = []
    k = IDX[at]
    while k < len(ALL) and ALL[k].address < end:
        ins = ALL[k]
        if ins.mnemonic in ("mov","mov.w") and len(ins.operands)==2 \
           and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_REG:
            s = ins.reg_name(ins.operands[1].reg); d = ins.reg_name(ins.operands[0].reg)
            if s in holds: holds.add(d)
        m = None
        if ins.operands and ins.operands[0].type == ARM_OP_MEM: m = ins.operands[0].mem
        elif len(ins.operands) >= 2 and ins.operands[1].type == ARM_OP_MEM: m = ins.operands[1].mem
        if m is not None and m.base and not m.index and ins.reg_name(m.base) in holds:
            t = (full + m.disp) & 0xFFFFFFFF
            if base <= t < base + 0x400:
                v = None
                for op in ins.operands:
                    if op.type == ARM_OP_IMM: v = op.imm & 0xFFFFFFFF
                rows.append((ins.address, ins.mnemonic, ins.op_str, t - base, ins.mnemonic.startswith("str"), v))
        k += 1
    if not rows: continue
    mp, nm = MASKS[base]
    print("\n  --- %s 基址物化 @ %08X (reg %s) 所在函数 %08X..%08X ---" % (name, at, r, at, end))
    for pc, mn, ops, d, isw, v in rows:
        rn = (mp.get(d, "+0x%X" % d) if mp else "+0x%X" % d)
        extra = ""
        if isw and v is not None:
            extra = "  val=0x%X" % v
        print("      %08X %-7s %-26s -> %-6s %s%s" % (pc, mn, ops, rn, "WRITE" if isw else "READ ", extra))
