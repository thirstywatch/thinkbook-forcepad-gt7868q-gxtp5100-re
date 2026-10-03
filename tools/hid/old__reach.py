"""verify-B/reach.py — 自研可达性：从复位向量出发，递归下降 + 跟踪 bl/blx/b/条件跳转
并报告：目标函数是否可达。同时对"间接调用（函数指针）"做保守处理：
  任何 str rX,[rY,#off] 写入 RAM 槽 + 后续 ldr rZ,[rY,#off]; blx rZ 的模式会被标记。
用法: python reach.py 0x0800FB00 0x08008B68 ...
"""
import struct, sys, collections
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
ADDRS = sorted(IDX)

def next_idx(a):
    k = IDX.get(a)
    return k

def linear_to(a):
    """返回从 a 起、直到无条件控制转移或返回为止的指令序列（含 a）"""
    out = []
    k = IDX.get(a)
    if k is None: return out
    while k < len(ALL):
        ins = ALL[k]
        out.append(ins)
        if ins.mnemonic in ("b","bx","pop","bl","blx") and "lr" not in ins.op_str:
            if ins.mnemonic in ("b",) or ins.mnemonic=="bx" or (ins.mnemonic=="pop" and "pc" in ins.op_str):
                break
        if ins.mnemonic == "bl":
            break
        k += 1
        if len(out) > 4000: break
    return out

def targets_of(ins):
    ts = []
    for op in ins.operands:
        if op.type == ARM_OP_IMM and ins.mnemonic in ("b","bl","cbz","cbnz","beq","bne","bhi","bls","bge","blt","bgt","ble","bhs","blo","bcs","bcc","bmi","bpl","bvs","bvc"):
            v = op.imm & 0xFFFFFFFF
            if A_LO <= (v & ~1) <= A_HI: ts.append(v & ~1)
    return ts

seen = set()
work = [0x08005164]
# 向量表全部条目（含 thumb 位掩码）
vec = []
for i in range(1, 60):
    v = rd32(A_LO + 4*i)
    if v and 0x08005000 <= v <= 0x08012342:
        vec.append(v & ~1)
work += vec

while work:
    st = work.pop()
    if st in seen or not (A_LO <= st <= A_HI): continue
    seq = linear_to(st)
    if not seq: continue
    seen.add(seq[0].address)
    for ins in seq:
        for t in targets_of(ins):
            if t not in seen: work.append(t)
        if ins.mnemonic in ("bl","blx") :
            for t in targets_of(ins):
                if t not in seen: work.append(t)

print("可达函数入口/基本块起点 %d 个" % len(seen))
print("向量表条目 %d 个: %s" % (len(vec), " ".join("%08X" % v for v in vec)))
print()
ok = 0
for arg in sys.argv[1:]:
    a = int(arg, 16)
    # 找 <= a 的最近可达点
    near = None
    for s in sorted(seen):
        if s <= a: near = s
        else: break
    hit = near is not None and (a - near) < 0x800
    print("  %08X  reachable=%s (最近可达点 %s, 距离 %s)" %
          (a, hit, ("%08X" % near) if near else "-", ("%d" % (a-near)) if near else "-"))

# 间接调用点
print()
print("="*88)
print("间接调用点（blx rN / bx rN）及其上下文的函数指针装载")
for ins in ALL:
    if ins.mnemonic in ("blx","bx") and ins.operands and ins.operands[0].type == ARM_OP_REG:
        rn = ins.reg_name(ins.operands[0].reg)
        if rn in ("lr","pc"): continue
        k = IDX[ins.address]
        ctx = ALL[max(0,k-6):k+1]
        print("  %08X  blx/bx %s   <- %s" % (ins.address, rn,
              " | ".join("%08X %s %s" % (x.address, x.mnemonic, x.op_str) for x in ctx[:-1])))
