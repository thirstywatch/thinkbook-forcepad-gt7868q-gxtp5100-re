# fw_deep11.py - 分析 0x08007CC0 (唯一未知的 LRA 结构引用者)
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

def decode_bl(off):
    if off + 4 > N: return None
    hw1 = struct.unpack_from("<H", img, off)[0]
    hw2 = struct.unpack_from("<H", img, off + 2)[0]
    if (hw1 & 0xF800) != 0xF000: return None
    if (hw2 & 0xD000) != 0xD000: return None
    S = (hw1 >> 10) & 1; imm10 = hw1 & 0x3FF
    J1 = (hw2 >> 13) & 1; J2 = (hw2 >> 11) & 1; imm11 = hw2 & 0x7FF
    I1 = (~(J1 ^ S)) & 1; I2 = (~(J2 ^ S)) & 1
    imm = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if imm & 0x1000000: imm -= 0x2000000
    return BASE + off + 4 + imm

cg = {}
for off in range(0, N - 4, 2):
    t = decode_bl(off)
    if t is not None and BASE <= t < BASE + N:
        cg.setdefault(t, []).append(BASE + off)

def show(a0, a1, title=""):
    print("\n--- %s 0x%08X..0x%08X ---" % (title, a0, a1))
    for i in insns:
        if i.address < a0: continue
        if i.address >= a1: break
        print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))

print("=== 0x08007CC0 的调用者 (字节级) ===")
print("  direct bl: %s" % ["0x%X" % x for x in cg.get(0x08007CC0, [])])
# 间接: 函数指针
pat = struct.pack("<I", 0x08007CC0 | 1)
s = 0; hits = []
while True:
    j = img.find(pat, s)
    if j < 0: break
    hits.append(BASE + j); s = j + 1
print("  函数指针(0x08007CC1)出现处: %s" % ["0x%X" % h for h in hits])
pat2 = struct.pack("<I", 0x08007CC0)
s = 0; hits2 = []
while True:
    j = img.find(pat2, s)
    if j < 0: break
    hits2.append(BASE + j); s = j + 1
print("  函数指针(0x08007CC0)出现处: %s" % ["0x%X" % h for h in hits2])

show(0x08007CC0, 0x08007D40, "fn_7CC0 head")
show(0x08007E40, 0x08007ED0, "LRA struct ref region")

print("\n=== 上溯 0x08007CC0 的调用链 (4 层) ===")
seen = set()
def up(t, d=0):
    if t in seen or d > 4: return
    seen.add(t)
    cs = cg.get(t, [])
    print("  " + "  " * d + "0x%08X <- %s" % (t, ["0x%X" % c for c in cs]))
    for c in cs:
        op = None
        best = None
        for i in insns:
            if i.address > c: break
            if i.mnemonic == "push" and "lr" in i.op_str: best = i.address
        up(best, d + 1)
up(0x08007CC0)
