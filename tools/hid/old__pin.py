"""verify-B/pin.py — 穷举 GPIO_SetBits/ResetBits 的 (端口, 引脚掩码) 组合
不强依赖函数边界：在每条 bl 到库函数前，向后回扫 12 条指令做局部常量替换。
"""
import struct, collections, re
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

# ---- 精确的 GPIO 标准库函数识别 ----
def fp(entry, n=14):
    return " | ".join("%s %s" % (ALL[k].mnemonic, ALL[k].op_str)
                      for k in range(IDX[entry], min(IDX[entry]+n, len(ALL))))
LIB = {}
for ins in ALL:
    if ins.mnemonic in ("sub","push"):
        e = ins.address
        txt = fp(e, 14)
        if re.search(r"ldr\s+r0, \[r1, #0x10\] \| bics r0, r2 \| str r0, \[r1, #0x10\]", txt):
            LIB[e] = "GPIO_ResetBits"
        elif re.search(r"ldr\s+r0, \[r1, #0xc\] \| orrs r0, r2 \| str r0, \[r1, #0xc\]", txt):
            LIB[e] = "GPIO_SetBits"
        elif re.search(r"ldr\s+r0, \[r0, #0xc\] \| ldr r1, \[sp, #4\] \| ands r0, r1", txt):
            LIB[e] = "GPIO_ReadOutputDataBit"
        elif re.search(r"ldr\s+r0, \[r0, #0x10\] \| ldr r1, \[sp, #4\] \| tst r0, r1", txt):
            LIB[e] = "GPIO_ReadInputDataBit?"
print("[0] 识别到的 GPIO 库函数入口：")
for e in sorted(LIB):
    print("    %08X %-22s  %s" % (e, LIB[e], fp(e, 9)))

GPORT = {0x40010800:"GPIOA",0x40010C00:"GPIOB",0x40011000:"GPIOC",
         0x40011400:"GPIOD",0x40011800:"GPIOE",0x40011C00:"GPIOF",0x40012000:"GPIOG"}

def local_consts(k, back=16):
    """从 k-1 向前回扫，返回 {reg: 常量}（最靠后的赋值胜出）"""
    regs = {}
    for j in range(k-1, max(-1, k-1-back), -1):
        x = ALL[j]
        if x.mnemonic in ("mov","movs","movw","movt") and len(x.operands)==2 \
           and x.operands[0].type==ARM_OP_REG and x.operands[1].type==ARM_OP_IMM:
            r = x.reg_name(x.operands[0].reg); v = x.operands[1].imm & 0xFFFFFFFF
            if x.mnemonic=="movw": cur = regs.get("__hi_"+r, 0)
            if r not in regs:
                if x.mnemonic=="movw": regs[r] = v & 0xFFFF
                elif x.mnemonic=="movt": regs[r] = (v & 0xFFFF) << 16
                else: regs[r] = v
            else:
                if x.mnemonic=="movw": regs[r] = (regs[r] & 0xFFFF0000) | (v & 0xFFFF)
                elif x.mnemonic=="movt": regs[r] = (regs[r] & 0xFFFF) | ((v & 0xFFFF) << 16)
                else: regs[r] = v
        elif x.mnemonic in ("add","adds","add.w") and len(x.operands)==3 \
             and x.operands[1].type==ARM_OP_REG and x.operands[1].type==ARM_OP_REG:
            try:
                d=x.reg_name(x.operands[0].reg); a1=x.reg_name(x.operands[1].reg)
                o2=x.operands[2]
                dv=(o2.imm if o2.type==ARM_OP_IMM else regs.get(x.reg_name(o2.reg) if o2.type==ARM_OP_REG else None))
                if a1 in regs and dv is not None: regs[d]=(regs[a1]+dv)&0xFFFFFFFF
            except Exception: pass
    return regs

print()
print("[1] 所有 GPIO_SetBits / ResetBits / ReadOutputDataBit 调用点的 (端口, 引脚掩码)")
combos = collections.defaultdict(list)
for k, ins in enumerate(ALL):
    if ins.mnemonic != "bl": continue
    m = re.match(r"#(0x[0-9a-f]+)", ins.op_str.strip())
    if not m: continue
    t = int(m.group(1), 16)
    if t not in LIB: continue
    regs = local_consts(k)
    r0 = regs.get("r0"); r1 = regs.get("r1")
    pname = GPORT.get(r0, ("0x%08X" % r0) if r0 is not None else "?")
    pin = ("0x%X" % r1) if r1 is not None else "?"
    pins = ""
    if r1 is not None:
        pins = ",".join("P%d" % i for i in range(32) if r1 & (1 << i)) or "0"
    combos[(LIB[t], pname, pin, pins)].append(ins.address)
for kk in sorted(combos):
    print("   %-24s %-10s mask=%-8s pins=%-14s x%d  @ %s" %
          (kk[0], kk[1], kk[2], kk[3], len(combos[kk]),
           " ".join("%08X" % x for x in combos[kk][:6])))
