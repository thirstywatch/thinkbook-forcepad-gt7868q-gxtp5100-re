# fw_deep9.py - 修正 BL 扫描 + 找触觉区域的指针表 + 找 LRA 结构引用点
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

def decode_bl(off):
    if off + 4 > N: return None
    hw1 = struct.unpack_from("<H", img, off)[0]
    hw2 = struct.unpack_from("<H", img, off + 2)[0]
    if (hw1 & 0xF800) != 0xF000: return None
    if (hw2 & 0xF800) != 0xF800: return None
    S = (hw1 >> 10) & 1; imm10 = hw1 & 0x3FF
    J1 = (hw2 >> 13) & 1; J2 = (hw2 >> 11) & 1; imm11 = hw2 & 0x7FF
    I1 = (~(J1 ^ S)) & 1; I2 = (~(J2 ^ S)) & 1
    imm = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if imm & 0x1000000: imm -= 0x2000000
    return BASE + off + 4 + imm

cg = {}
for off in range(0, N - 4, 2):
    t = decode_bl(off)
    if t is None: continue
    if BASE <= t < END:
        cg.setdefault(t, []).append(BASE + off)
print("BL 调用图: %d 目标, %d 条边" % (len(cg), sum(len(v) for v in cg.values())))

def callers(t):
    return cg.get(t, [])

starts = sorted(set(i.address for i in insns if i.mnemonic == "push" and "lr" in i.op_str))
def owner(a):
    best = None
    for s in starts:
        if s <= a: best = s
        else: break
    return best

# --- 1) 触觉区域内的函数 & 它们的调用者 ---
print("\n=== 触觉区域 0x08008600-0x08009800 内的函数及其调用者 ===")
for s in starts:
    if 0x08008600 <= s < 0x08009800:
        cs = callers(s)
        print("  fn 0x%08X  callers=%s" % (s, ["0x%X" % c for c in cs]))

# --- 2) 0x08008628 / 0x08008858 的上溯 ---
print("\n=== 上溯: 谁调用 0x08008628 (启动震动) ===")
def up(t, depth=0, maxd=4, seen=None):
    if seen is None: seen = set()
    if t in seen or depth > maxd: return
    seen.add(t)
    cs = callers(t)
    print("  " + "  " * depth + "fn 0x%08X <- %s" % (t, ["0x%X" % c for c in cs]))
    for c in cs:
        o = owner(c)
        if o: up(o, depth + 1, maxd, seen)
up(0x08008628)
print("\n=== 上溯: 谁调用 0x08008858 ===")
up(0x08008858)
print("\n=== 上溯: 谁调用 0x200040D0 结构所在函数的邻居 0x0800865C+ ===")
for s in starts:
    if 0x0800865C <= s < 0x08008800:
        print("  fn 0x%08X callers=%s" % (s, ["0x%X" % c for c in callers(s)]))

# --- 3) 数据区里指向触觉区域的 32 位指针 (函数指针表) ---
print("\n=== 数据区中指向 0x08008600-0x08009800 的 32 位指针 ===")
found = 0
for off in range(0, N - 4, 2):
    v = struct.unpack_from("<I", img, off)[0]
    if 0x08008600 <= (v & ~1) < 0x08009800:
        print("  0x%08X : 0x%08X  (owner fn 0x%08X)" % (BASE + off, v, owner(BASE + off) or 0))
        found += 1
        if found > 40: break
if not found: print("  (无)")

# --- 4) LRA 结构 0x200040D0 / 0x200040B8 的引用点 ---
print("\n=== LRA 结构 0x200040D0 / 0x200040B8 引用点 ===")
for tgt in (0x200040D0, 0x200040B8):
    pat = struct.pack("<I", tgt)
    s = 0; hits = []
    while True:
        j = img.find(pat, s)
        if j < 0: break
        hits.append(BASE + j); s = j + 1
    print("  0x%08X : %s" % (tgt, ["0x%X" % h for h in hits[:14]]))
