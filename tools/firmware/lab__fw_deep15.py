# fw_deep15.py - 挖 0xA2/0xA5 魔数帧的所有构造点 (主MCU <-> 第二芯片 私有协议)
from capstone import *

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

MAGIC = ("0xa2", "0xa5", "0x5a", "0x2a", "0xa1", "0x1a", "0xc3", "0x3c", "0x5c", "0xc5")
print("=== 魔数字节写入点 (movs rX,#magic 后紧接 strb/str) ===")
cnt = 0
for k, i in enumerate(insns):
    if not i.mnemonic.startswith("mov"): continue
    o = i.op_str
    if "," not in o: continue
    imm = o.split(",")[-1].strip()
    if imm not in MAGIC: continue
    nxt = insns[k+1:k+3]
    if not any(t.mnemonic.startswith("str") for t in nxt): continue
    print("   --- 0x%08X (fn 0x%08X): %s %s ---" % (i.address, owner(i.address) or 0, i.mnemonic, o))
    for t in insns[max(0, k-3):k+4]:
        print("       %08X: %-10s %s" % (t.address, t.mnemonic, t.op_str))
    cnt += 1
    if cnt >= 14: break
print("   total shown=%d" % cnt)

print("\n=== 所有对 GPIOA(0x40010800) / 0x40010C00 的引用点所属函数 ===")
gp = {}
for k, i in enumerate(insns):
    if "0x40010800" in i.op_str or "0x40010c00" in i.op_str:
        f = owner(i.address)
        gp.setdefault(f, []).append(i.address)
for f, ats in sorted(gp.items(), key=lambda kv: -len(kv[1]))[:12]:
    print("   fn 0x%08X  refs=%d  sites=%s" % (f or 0, len(ats), ["0x%X" % a for a in ats[:8]]))

print("\n=== 0x08008868 完整体 (帧构造函数) ===")
c = 0
for i in insns:
    if i.address < 0x08008868: continue
    if i.mnemonic == "pop" and "pc" in i.op_str:
        print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str)); break
    print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))
    c += 1
    if c > 45: break
