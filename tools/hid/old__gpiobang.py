"""verify-B/gpiobang.py — 穷举所有 GPIOx 的 BSRR/BRR/ODR/CRL/CRH 写点，判定 bit-bang
方法：全局搜索 4 字节立即数或 movw/movt 得到的 0x40010800..0x400123FF 基址，
然后在其所在函数窗口内列出写操作（含 mov 传递）。
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
ENTRIES = sorted([ins.address for ins in ALL if ins.mnemonic == "push"] +
                 [0x08005164,0x0800A678,0x08008894,0x0800A448,0x080053F4,0x0800DFE4,
                  0x0800BE24,0x080053F8,0x0800B75C,0x0800CE7C,0x08006B3C,0x0800D628,
                  0x08008978,0x0800894C,0x0800DEE8])
ENTRIES = sorted(set(ENTRIES))
def fnend(x):
    for e in ENTRIES:
        if e > x: return e
    return A_HI+1

GP = {0x40010800:"GPIOA",0x40010C00:"GPIOB",0x40011000:"GPIOC",
      0x40011400:"GPIOD",0x40011800:"GPIOE",0x40011C00:"GPIOF",0x40012000:"GPIOG"}
GR = {0x00:"CRL",0x04:"CRH",0x08:"IDR",0x0C:"ODR",0x10:"BSRR",0x14:"BRR",0x18:"LCKR"}
BITS = {}
for i in range(16):
    BITS[1<<i] = "P%d" % i
    BITS[1<<(i+16)] = "RESET_P%d" % i

# 收集所有 GPIO 基址物化（movw/movt 配对 或 ldr 池）
found = []
lastw = {}
for k, ins in enumerate(ALL):
    if ins.mnemonic == "movw" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        lastw[ins.reg_name(ins.operands[0].reg)] = (ins.address, ins.operands[1].imm & 0xFFFF)
    elif ins.mnemonic == "movt" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg)
        if r in lastw:
            wa, lo = lastw.pop(r)
            found.append((wa, ins.address, r, (lo | ((ins.operands[1].imm & 0xFFFF)<<16)) & 0xFFFFFFFF))
        else:
            found.append((None, ins.address, r, ((ins.operands[1].imm & 0xFFFF)<<16) & 0xFFFFFFFF))
for ins in ALL:
    if ins.mnemonic == "ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_MEM and ins.operands[1].mem.base \
       and ins.reg_name(ins.operands[1].mem.base)=="pc":
        v = rd32(((ins.address+4)&~3)+ins.operands[1].mem.disp)
        if v is not None:
            found.append((None, ins.address, ins.reg_name(ins.operands[0].reg), v))

print("="*92)
print("[1] 所有 GPIO 端口基址物化点")
for wa, at, r, full in sorted(found, key=lambda x: x[1]):
    for b, nm in GP.items():
        if b <= full <= b + 0x400:
            print("   %08X %-6s -> 0x%08X  (%s+0x%X)  reg=%s" % (at, nm, full, nm, full-b, r))

print()
print("="*92)
print("[2] 所有对 GPIOx_BSRR / BRR / ODR / CRL / CRH 的写操作（bit-bang 判定核心）")
rows = []
for wa, at, r, full in sorted(found, key=lambda x: x[1]):
    base = None
    for b, nm in GP.items():
        if b <= full < b + 0x400:
            base = b; nm2 = nm; break
    if base is None or full != base: continue
    end = fnend(at)
    holds = {r}
    k = IDX.get(at)
    if k is None: continue
    while k < len(ALL) and ALL[k].address < end:
        ins = ALL[k]
        if ins.mnemonic in ("mov","mov.w") and len(ins.operands)==2 \
           and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_REG:
            s=ins.reg_name(ins.operands[1].reg); d=ins.reg_name(ins.operands[0].reg)
            if s in holds: holds.add(d)
        m = None
        if ins.operands and ins.operands[0].type==ARM_OP_MEM: m = ins.operands[0].mem
        elif len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_MEM: m = ins.operands[1].mem
        if m is not None and m.base and not m.index and ins.mnemonic.startswith("str") \
           and ins.reg_name(m.base) in holds:
            t = (base + m.disp) & 0xFFFFFFFF
            if base <= t <= base + 0x18 and (t-base) in GR:
                v = None
                for op in ins.operands:
                    if op.type == ARM_OP_IMM: v = op.imm & 0xFFFFFFFF
                rows.append((ins.address, ins.mnemonic, ins.op_str, nm2, GR[t-base], v))
        k += 1
cnt = collections.Counter((x[3], x[4]) for x in rows)
for kk in sorted(cnt):
    print("   %-6s %-5s 写 x%d" % (kk[0], kk[1], cnt[kk]))
print()
for pc, mn, ops, port, reg, v in sorted(set(rows)):
    extra = ""
    if v is not None and reg in ("BSRR","BRR","ODR"):
        extra = "  常量=0x%X (%s)" % (v, ", ".join(BITS[b] for b in BITS if v & b) or "0")
    print("   %08X %-7s %-28s %s.%s%s" % (pc, mn, ops, port, reg, extra))
