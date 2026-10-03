# fw_deep10.py - 找 LRA 结构的 movw/movt 引用点 + 找跳转(b)到震动函数的点
import struct
from capstone import *

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
img = data[0x19ABC:]
BASE = 0x08000000
N = len(img)

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

# --- 1) movw/movt 物化的 32 位常量 -> 引用点 ---
WANT = {0x200040D0: "LRA struct", 0x200040B8: "struct_B8", 0x2000403C: "s_403C",
        0x20003F70: "s_3F70", 0x20003FD0: "s_3FD0", 0x20004128: "s_4128"}
mats = {}
pending = {}
for ins in insns:
    o = ins.op_str
    try:
        if ins.mnemonic.startswith("movw") and "#" in o:
            reg = o.split(",")[0].strip(); pending[reg] = (int(o.split("#")[1], 0), ins.address)
        elif ins.mnemonic.startswith("movt") and "#" in o:
            reg = o.split(",")[0].strip()
            if reg in pending:
                lo, at = pending.pop(reg)
                v = (int(o.split("#")[1], 0) << 16) | (lo & 0xFFFF)
                mats.setdefault(v, []).append(at)
    except Exception:
        pass

print("=== LRA 结构 / 关键 SRAM 的 movw+movt 引用点 ===")
for v, nm in WANT.items():
    ats = mats.get(v, [])
    print("\n  %-12s 0x%08X  refs=%d" % (nm, v, len(ats)))
    for a in ats:
        print("      site 0x%08X   fn 0x%08X" % (a, owner(a) or 0))

# --- 2) 所有跳转指令的目标命中触觉区域 ---
print("\n=== 跳转(b/b.w/条件跳转) 命中 0x08008600-0x08008800 的点 ===")
cnt = 0
for i in insns:
    if not i.mnemonic.startswith("b"): continue
    if i.mnemonic in ("bl", "blx", "bic", "bfc", "bfi", "bkpt"): continue
    if not i.op_str.startswith("#"): continue
    try: t = int(i.op_str[1:], 16)
    except Exception: continue
    if 0x08008600 <= t < 0x08008800:
        print("    0x%08X  %-8s -> 0x%08X   (fn 0x%08X)" % (i.address, i.mnemonic, t, owner(i.address) or 0))
        cnt += 1
        if cnt > 30: break
if cnt == 0: print("    (无)")

# --- 3) 0x0800D6F4 / 0x0800D6xx 区域的跳转引用 ---
print("\n=== 跳转命中 0x0800D600-0x0800D800 (波形/ISR) ===")
cnt = 0
for i in insns:
    if not i.mnemonic.startswith("b"): continue
    if i.mnemonic in ("bl", "blx", "bic", "bfc", "bfi", "bkpt"): continue
    if not i.op_str.startswith("#"): continue
    try: t = int(i.op_str[1:], 16)
    except Exception: continue
    if 0x0800D600 <= t < 0x0800D800:
        print("    0x%08X  %-8s -> 0x%08X   (fn 0x%08X)" % (i.address, i.mnemonic, t, owner(i.address) or 0))
        cnt += 1
        if cnt > 20: break
if cnt == 0: print("    (无)")
