# fw_deep14.py - 用"ldrh [buf,#6] + ldrh [buf,#8]"指纹找 0x20 内存命令处理器
from capstone import *
import collections

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
img = data[0x19ABC:]
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))

starts = sorted(set(i.address for i in insns if i.mnemonic == "push" and "lr" in i.op_str))
def owner(a):
    best = None
    for s in starts:
        if s <= a: best = s
        else: break
    return best

# 收集每个函数内的 ldrh [reg, #imm]
per = collections.defaultdict(list)
for i in insns:
    if not i.mnemonic.startswith("ldrh"): continue
    if "#" not in i.op_str: continue
    try:
        reg = i.op_str.split("[")[1].split(",")[0].strip()
        imm = int(i.op_str.split("#")[1].split("]")[0], 0)
    except Exception:
        continue
    f = owner(i.address)
    if f: per[f].append((i.address, reg, imm))

print("=== 候选: 同一函数内对同一基址寄存器取 #a 与 #a+2 两个半字 ===")
cands = []
for f, lst in per.items():
    byreg = collections.defaultdict(set)
    for a, reg, imm in lst:
        byreg[reg].add(imm)
    for reg, imms in byreg.items():
        for x in sorted(imms):
            if x + 2 in imms and x <= 12:
                cands.append((f, reg, x, x + 2))
                break
seen = set()
for f, reg, a, b in sorted(cands):
    if f in seen: continue
    seen.add(f)
    print("  fn 0x%08X   reg=%s  offsets #%d / #%d" % (f, reg, a, b))

print("\n=== 候选函数反汇编 (前 70 条) ===")
for f, reg, a, b in sorted(set(cands))[:6]:
    print("\n----- fn 0x%08X (offsets #%d/#%d in %s) -----" % (f, a, b, reg))
    c = 0
    for i in insns:
        if i.address < f: continue
        if i.mnemonic == "pop" and "pc" in i.op_str and i.address > f:
            print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str)); break
        print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))
        c += 1
        if c >= 70: break
