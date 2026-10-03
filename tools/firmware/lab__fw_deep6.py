# fw_deep6.py - 展开 TIM3 使用点 + 震动调用点上下文
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

def win(a0, a1, title):
    print("\n" + "=" * 72)
    print("### %s  0x%08X..0x%08X" % (title, a0, a1))
    for i in insns:
        if i.address < a0: continue
        if i.address >= a1: break
        mark = "  <<<< TIM3" if (i.mnemonic.startswith(("ldr", "str")) and "0x40000400" in i.op_str) else ""
        print("  %08X: %-10s %s%s" % (i.address, i.mnemonic, i.op_str, mark))

def callers(t):
    o = []
    for i in insns:
        if i.mnemonic in ("bl", "blx") and i.op_str.startswith("#"):
            try:
                if int(i.op_str[1:], 16) == t: o.append(i.address)
            except Exception: pass
    return o

# 已知函数边界(用 pop pc / bx lr 找端点)
def extent(a0, limit=0x600):
    last = a0
    for i in insns:
        if i.address < a0: continue
        if i.address > a0 + limit: break
        if (i.mnemonic == "pop" and "pc" in i.op_str) or (i.mnemonic == "bx" and i.op_str == "lr"):
            last = i.address
            break
    return last

for a, nm in ((0x08008628, "TIM3 user #1"), (0x0800B9DC, "TIM3 user #2")):
    e = extent(a)
    print("\n@@@@ %s fn=0x%08X .. 0x%08X  callers=%s" % (nm, a, e, ["0x%X" % x for x in callers(a)]))
    win(a, min(e + 6, a + 0x200), nm)

print("\n\n@@@@ 震动调用点上下文 @0x0800AD20 ------------------------------------")
win(0x0800AD20, 0x0800AE00, "vibration call site")

print("\n@@@@ 函数 0x0800AA20 的尾部/边界检查 ---------------------------------")
print("   callers(0x0800AA20) = %s" % ["0x%X" % x for x in callers(0x0800AA20)])
print("   extent = 0x%08X" % extent(0x0800AA20, 0x1000))

print("\n@@@@ 谁调用 0x08009750 / 0x08008FE8 / 0x08008628 / 0x0800B9DC --------")
for t in (0x08009750, 0x08008FE8, 0x08008628, 0x0800B9DC, 0x08008704):
    print("   0x%08X <- %s" % (t, ["0x%X" % x for x in callers(t)]))
