"""verify-B/bitbang_final.py — 判定性检查：是否存在 GPIO 引脚级 bit-bang
(1) 全镜像 GPIOC/GPIOD/GPIOE/GPIOF/GPIOG 常量的所有出现（含 movw+movt 与字面量池）
(2) 对这些常量所在位置做有界反向切片，求 (r0,r1) 常量
(3) 是否存在任何对 GPIO 块内 ODR/BSRR/BRR 的写入（直接或库函数）
"""
import struct, collections, re
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

GPORT = {0x40010800:"GPIOA",0x40010C00:"GPIOB",0x40011000:"GPIOC",
         0x40011400:"GPIOD",0x40011800:"GPIOE",0x40011C00:"GPIOF",0x40012000:"GPIOG"}
PREF = {0x40010800:0x0800,0x40010C00:0x0C00,0x40011000:0x1000,
        0x40011400:0x1400,0x40011800:0x1800,0x40011C00:0x1C00,0x40012000:0x2000}

def backslice(k, back=60):
    """有界反向切片：从 k-1 向前，遇到块终止符停；返回可证明为常量的 {reg:值}"""
    regs = {}
    for j in range(k-1, max(-1, k-1-back), -1):
        x = ALL[j]
        if x.mnemonic in ("mov","movs","movw","movt") and len(x.operands)==2 \
           and x.operands[0].type==ARM_OP_REG and x.operands[1].type==ARM_OP_IMM:
            r=x.reg_name(x.operands[0].reg); v=x.operands[1].imm & 0xFFFFFFFF
            if x.mnemonic=="movw": regs[r]=(regs.get(r,0)&0xFFFF0000|(v&0xFFFF))
            elif x.mnemonic=="movt": regs[r]=(regs.get(r,0)&0xFFFF)|((v&0xFFFF)<<16)
            else: regs[r]=v
        elif x.mnemonic=="mov" and len(x.operands)==2 and \
             all(o.type==ARM_OP_REG for o in x.operands):
            s=x.reg_name(x.operands[1].reg); d=x.reg_name(x.operands[0].reg)
            if s in regs: regs[d]=regs[s]
            else: regs.pop(d, None)
        elif x.mnemonic in ("b","bx") and not x.op_str.strip().startswith("#"):
            break
        elif x.mnemonic=="pop" and "pc" in x.op_str:
            break
    return regs

# (1) 找所有 GPIOC/GPIOD/GPIOE/GPIOF/GPIOG 常量出现
print("="*96)
print("[1] GPIOC/D/E/F/G 常量出现点及其有界反向切片")
occ = []
reg = {}
for ins in ALL:
    if ins.mnemonic in ("mov","movs","movw","movt") and len(ins.operands)==2 \
       and ins.operands[0].type==ARM_OP_REG and ins.operands[1].type==ARM_OP_IMM:
        r=ins.reg_name(ins.operands[0].reg); v=ins.operands[1].imm & 0xFFFFFFFF
        if ins.mnemonic=="movw": reg[r]=(reg.get(r,0)&0xFFFF0000|(v&0xFFFF))
        elif ins.mnemonic=="movt": reg[r]=(reg.get(r,0)&0xFFFF)|((v&0xFFFF)<<16)
        else: reg[r]=v
        if reg[r] in GPORT: occ.append((ins.address, GPORT[reg[r]]))
    elif ins.mnemonic=="ldr" and len(ins.operands)==2 and ins.operands[0].type==ARM_OP_REG \
       and ins.operands[1].type==ARM_OP_MEM and ins.operands[1].mem.base \
       and ins.reg_name(ins.operands[1].mem.base)=="pc":
        v=rd32(((ins.address+4)&~3)+ins.operands[1].mem.disp)
        if v in GPORT: occ.append((ins.address, GPORT[v]))
print("   共 %d 处: %s" % (len(occ), collections.Counter(x[1] for x in occ)))

# (2) 对每个出现点，看它之后 30 条里是否出现对 GPIO 块内 0x0C/0x10/0x14 的写
print()
print("[2] 这些出现点之后 30 条指令内对 GPIO 块 +0x0C/0x10/0x14/+0x30 的访存")
found = 0
for at, nm in occ:
    k = IDX[at]
    for j in range(k, min(k+30, len(ALL))):
        x = ALL[j]
        m=None
        if x.operands and x.operands[0].type==ARM_OP_MEM: m=x.operands[0].mem
        elif len(x.operands)>=2 and x.operands[1].type==ARM_OP_MEM: m=x.operands[1].mem
        if m is not None and m.base and not m.index and m.disp in (0x0C,0x10,0x14,0x30,0x34):
            print("   %s @%08X -> %08X %-8s %-26s +0x%X %s" % (nm, at, x.address, x.mnemonic,
                  x.op_str, m.disp, "WRITE" if x.mnemonic.startswith("str") else "READ"))
            found += 1
            break
if found == 0: print("   (无)")

# (3) 找 bl 到 0x08010BDC(ResetBits) / 0x08010D1C(SetBits) / 0x08010D30(ResetBits) / 0x08010D44 的站点
print()
print("[3] GPIO 位操作库函数调用点及 (r0,r1)")
for tgt in (0x08010BDC, 0x08010CFC, 0x08010D1C, 0x08010D30, 0x08010D44):
    sites = []
    for k, ins in enumerate(ALL):
        if ins.mnemonic=="bl":
            mm = re.match(r"#(0x[0-9a-f]+)", ins.op_str.strip())
            if mm and int(mm.group(1),16) == tgt:
                sites.append(k)
    print("   -> %08X  x%d" % (tgt, len(sites)))
    for k in sites:
        regs = backslice(k, 40)
        r0 = regs.get("r0"); r1 = regs.get("r1")
        p = GPORT.get(r0, ("0x%08X" % r0) if r0 is not None else "?")
        pin = ("P%s" % ",".join(str(i) for i in range(32) if r1 & (1<<i))) if r1 is not None else "?"
        print("        %08X  r0=%s(%s)  r1=%s(%s)" %
              (ALL[k].address, p, ("0x%08X"%r0) if r0 is not None else "?", pin,
               ("0x%X"%r1) if r1 is not None else "?"))
