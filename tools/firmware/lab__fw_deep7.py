# fw_deep7.py - 搜 LRA 专属常量(119/999/1999)的写入点 + 调用点上下文 + 函数指针表
import struct
from capstone import *

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
img = data[0x19ABC:]
BASE = 0x08000000
N = len(img)
END = BASE + N
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))

def callers(t):
    o = []
    for i in insns:
        if i.mnemonic in ("bl", "blx") and i.op_str.startswith("#"):
            try:
                if int(i.op_str[1:], 16) == t: o.append(i.address)
            except Exception: pass
    return o

def win(a0, a1, title=""):
    print("\n--- %s 0x%08X..0x%08X ---" % (title, a0, a1))
    for i in insns:
        if i.address < a0: continue
        if i.address >= a1: break
        print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))

print("=== A) 常量 119 / 999 / 1999 的立即数出现点 ===")
for i in insns:
    o = i.op_str
    if "#" not in o: continue
    vals = []
    for part in o.split("#")[1:]:
        try: vals.append(int(part.split(",")[0].strip(), 0))
        except Exception: pass
    for v in vals:
        if v in (119, 999, 1999, 0x77, 0x3E7, 0x7CF):
            print("  0x%08X  %-10s %s" % (i.address, i.mnemonic, o))

print("\n=== B) 关键函数调用者 ===")
for t, nm in ((0x08008858, "fn_8858(LRA struct)"), (0x0800903E, "init site"),
              (0x08009784, "runtime site"), (0x0800D628, "TIM3 ISR"),
              (0x08009750, "LRA cfg"), (0x08008FE8, "TIM2 init"),
              (0x08008628, "TIM3 user#1"), (0x0800AA20, "big fn")):
    print("  %-22s 0x%08X <- %s" % (nm, t, ["0x%X" % x for x in callers(t)]))

print("\n=== C) 数据区的代码指针 (含非 Thumb 位) ===")
for t, nm in ((0x08008628, "TIM3 user#1"), (0x0800AA20, "big fn"), (0x08008858, "fn_8858"),
              (0x0800D628, "TIM3 ISR"), (0x0800903E, "init"), (0x08009750, "LRA cfg")):
    for bit in (1, 0):
        pat = struct.pack("<I", t | bit)
        s = 0
        hits = []
        while True:
            j = img.find(pat, s)
            if j < 0: break
            hits.append(BASE + j); s = j + 1
        if hits:
            print("  0x%08X|%d 找到 %d 处: %s" % (t, bit, len(hits), ["0x%X" % h for h in hits[:8]]))

print("\n=== D) 震动调用点上下文 0x0800AD40..0x0800ADB0 ===")
win(0x0800AD40, 0x0800ADB0, "vibration callsite")

print("\n=== E) 0x08008858 函数体 ===")
win(0x08008858, 0x080088E0, "fn_8858")
