"""verify-B/scanim.py — 独立：扫描全段指令的立即数/字面量，找出所有外设区地址的"物化点"
不依赖 asm.txt；用 capstone 从 bin 重新解码，枚举 16 个寄存器目标以确保不漏。
"""
import struct, sys, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

BIN = r"<WORKSPACE>"
A_LO, A_HI = 0x08005000, 0x08012342
F_LO = 0x19ABC
data = open(BIN, "rb").read()

def off(a): return a - A_LO + F_LO
def rd32(a):
    o = off(a)
    if o < 0 or o + 4 > len(data): return None
    return struct.unpack_from("<I", data, o)[0]

md32 = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md32.detail = True
md16 = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md16.detail = True

def decode_all(lo, hi, th):
    """线性解码，th=16 时只收 16 位指令"""
    out = []
    a = lo
    while a <= hi - 1:
        o = off(a)
        chunk = data[o:o + 4]
        if len(chunk) < 2: break
        best = None
        for ins in md32.disasm(chunk, a):
            best = ins; break
        if best is None:
            a += 2; continue
        if th == 16 and best.size != 2:
            a += 2; continue
        out.append(best)
        a += best.size
    return out

ALL = decode_all(A_LO, A_HI, 0)
print("独立解码指令数 %d，地址 %08X..%08X" % (len(ALL), ALL[0].address, ALL[-1].address))

# ---- 1) 所有立即数 0x40000000-0x4003FFFF 的物化点 ----
print("\n[A] 指令内立即数落在外设区的（movw/movt/mov/add.w/ldr=?）")
PER_LO, PER_HI = 0x40000000, 0x4003FFFF
imm_hits = collections.defaultdict(list)
for ins in ALL:
    for op in ins.operands:
        if op.type == ARM_OP_IMM:
            v = op.imm & 0xFFFFFFFF
            if PER_LO <= v <= PER_HI:
                imm_hits[v].append((ins.address, ins.mnemonic, ins.op_str))
for v in sorted(imm_hits):
    hs = imm_hits[v]
    print("  0x%08X x%d: %s" % (v, len(hs),
          "; ".join("%08X %s %s" % h for h in hs[:8])))
if not imm_hits:
    print("  (无)")

# ---- 2) PC 相对 ldr 池值落在外设区 ----
print("\n[B] PC 相对 ldr 从字面量池取到的外设区地址")
pool_hits = collections.defaultdict(list)
for ins in ALL:
    if ins.mnemonic not in ("ldr",): continue
    if len(ins.operands) != 2: continue
    o0, o1 = ins.operands
    if o0.type != ARM_OP_REG or o1.type != ARM_OP_MEM: continue
    m = o1.mem
    if not m.base or ins.reg_name(m.base) != "pc": continue
    va = ((ins.address + 4) & ~3) + m.disp
    v = rd32(va)
    if v is None: continue
    if PER_LO <= v <= PER_HI:
        pool_hits[v].append((ins.address, ins.reg_name(o0.reg), va))
for v in sorted(pool_hits):
    hs = pool_hits[v]
    print("  0x%08X x%d: %s" % (v, len(hs),
          "; ".join("%08X ldr %s,[%08X]" % h for h in hs[:8])))
if not pool_hits:
    print("  (无)")

# ---- 3) 所有 movw/movt 立即数分布（看 0x4000 半字） ----
print("\n[C] movt 立即数分布（>0x3FFF 的）")
c = collections.Counter()
for ins in ALL:
    if ins.mnemonic == "movt" and len(ins.operands) == 2 and ins.operands[1].type == ARM_OP_IMM:
        c[ins.operands[1].imm & 0xFFFF] += 1
for v, n in sorted(c.items()):
    if v >= 0x3F00:
        print("  movt #0x%04X x%d" % (v, n))

print("\n[D] movw 立即数在 0x5000-0x6000 与 0x0000-0x0400 区间的")
c2 = collections.Counter()
for ins in ALL:
    if ins.mnemonic == "movw" and len(ins.operands) == 2 and ins.operands[1].type == ARM_OP_IMM:
        v = ins.operands[1].imm & 0xFFFF
        if 0x5000 <= v <= 0x6000 or v <= 0x0400:
            c2[v] += 1
for v, n in sorted(c2.items()):
    print("  movw #0x%04X x%d" % (v, n))
