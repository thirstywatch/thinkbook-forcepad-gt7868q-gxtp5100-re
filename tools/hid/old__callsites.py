"""verify-B/callsites.py — 找 GPIO_SetBits/ResetBits/WriteBit/ReadInputDataBit 的实际调用点
先反汇编求出每个 GPIO 库函数的入口，再在全镜像找 bl 到这些入口的站点，
并回溯该站点的 r0/r1（端口基址 / 引脚掩码）。
"""
import struct, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM
BIN = r"<WORKSPACE>"
A_LO, A_HI, F_LO = 0x08005000, 0x08012342, 0x19ABC
data = open(BIN, "rb").read()
def off(a): return a - A_LO + F_LO
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.detail = True
ALL = []
a = A_LO
while a <= A_HI:
    ok=False
    for ins in md.disasm(data[off(a):off(a)+4], a):
        ALL.append(ins); a += ins.size; ok=True; break
    if not ok: a += 2
IDX = {ins.address: k for k, ins in enumerate(ALL)}

# 用"访问偏移集合"自动识别 GPIO 位操作函数
GP = {0x40010800:"GPIOA",0x40010C00:"GPIOB",0x40011000:"GPIOC",
      0x40011400:"GPIOD",0x40011800:"GPIOE"}
def fn_offsets(entry, limit=40):
    offs = []
    k = IDX[entry]
    for i in range(k, min(k+limit, len(ALL))):
        ins = ALL[i]
        m=None
        if ins.operands and ins.operands[0].type==ARM_OP_MEM: m=ins.operands[0].mem
        elif len(ins.operands)>=2 and ins.operands[1].type==ARM_OP_MEM: m=ins.operands[1].mem
        if m is not None and m.base and not m.index:
            offs.append((ins.mnemonic, m.disp))
        if ins.mnemonic=="bx" and ins.op_str.strip()=="lr": break
    return offs

print("="*96)
print("[1] 自动识别 GPIO 位操作库函数（扫描所有 sub sp,#N / push 入口，看偏移签名）")
CAND = {}
for ins in ALL:
    if ins.mnemonic in ("sub","push"):
        e = ins.address
        offs = fn_offsets(e, 40)
        ds = [d for m,d in offs]
        # GPIO_SetBits: ODR(0x0C) 读 + BSRR(0x10) 写 ; ResetBits: BSRR(0x10) 读 + BRR(0x14) 写
        sig = tuple(sorted(set(ds)))
        mn = [m for m,d in offs]
        if 0x10 in ds and 0x14 in ds and any(x.startswith("str") for x in mn):
            CAND[e] = "GPIO_ResetBits(BSRR/BRR)"
        elif 0x0C in ds and 0x10 in ds and "bics" in mn:
            CAND[e] = "GPIO_SetBits(ODR/BSRR)"
        elif 0x0C in ds and 0x10 in ds and "ands" in mn:
            CAND[e] = "GPIO_ReadOutputDataBit"
        elif ds == [0x08] or (0x08 in ds and len(ds)<=2):
            CAND[e] = "GPIO_ReadInputData*"
for e in sorted(CAND):
    print("   %08X  %-28s  offsets=%s" % (e, CAND[e],
          [d for m,d in fn_offsets(e)]))

print()
print("="*96)
print("[2] 上述 GPIO 函数的调用点 + 回溯 r0(端口)/r1(引脚掩码)")
names = {}
lastw = {}
for k, ins in enumerate(ALL):
    if ins.mnemonic=="movw" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        lastw[ins.reg_name(ins.operands[0].reg)] = ins.operands[1].imm & 0xFFFF
    elif ins.mnemonic=="movt" and len(ins.operands)==2 and ins.operands[1].type==ARM_OP_IMM:
        r = ins.reg_name(ins.operands[0].reg)
        lo = lastw.pop(r) if r in lastw else 0
        v = (lo | ((ins.operands[1].imm & 0xFFFF)<<16)) & 0xFFFFFFFF
        if v in GP:
            # 记录该物化点，供后面 bl 站点回溯
            names.setdefault(k, (v, k))

for tgt in sorted(CAND):
    sites = []
    for k, ins in enumerate(ALL):
        if ins.mnemonic in ("bl","b.w") and ins.op_str.strip().startswith("#0x%x" % tgt):
            sites.append(k)
    print("\n   --- %08X %s  调用点 %d 个 ---" % (tgt, CAND[tgt], len(sites)))
    for k in sites[:200]:
        ctx = ALL[max(0,k-8):k+1]
        # 回溯 r0/r1
        def back(regname, n=10):
            j = k-1; cnt=0
            while j >= 0 and cnt < n:
                x = ALL[j]
                if x.mnemonic in ("movw","movt","mov","movs") and x.operands \
                   and x.operands[0].type==ARM_OP_REG and x.reg_name(x.operands[0].reg)==regname:
                    if x.operands[1].type==ARM_OP_IMM: return "0x%X" % (x.operands[1].imm & 0xFFFFFFFF)
                    if x.operands[1].type==ARM_OP_REG: return "(%s)" % x.reg_name(x.operands[1].reg)
                j -= 1; cnt += 1
            return "?"
        r0 = back("r0"); r1 = back("r1")
        print("      %08X  r0=%s r1=%s   %s" % (ALL[k].address, r0, r1,
              " | ".join("%s %s" % (x.mnemonic, x.op_str) for x in ctx[-4:])))
