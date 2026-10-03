# fw_deep13.py - 追真正活的波形路径 0x080086B4 及其触发源
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

starts = sorted(set(i.address for i in insns if i.mnemonic == "push" and "lr" in i.op_str))
def owner(a):
    best = None
    for s in starts:
        if s <= a: best = s
        else: break
    return best

# ISR 集合(向量表)
isr = {}
for k in range(2, 60):
    o = 4 * k
    if o + 4 > N: break
    v = struct.unpack_from("<I", img, o)[0]
    if v and 0x08000000 <= (v & ~1) < BASE + N:
        isr[v & ~1] = "vec[%d]" % k

def show(a0, a1, title=""):
    print("\n--- %s 0x%08X..0x%08X ---" % (title, a0, a1))
    for i in insns:
        if i.address < a0: continue
        if i.address >= a1: break
        extra = "   <== ISR %s" % isr[i.address] if i.address in isr else ""
        print("  %08X: %-10s %s%s" % (i.address, i.mnemonic, i.op_str, extra))

show(0x080086B4, 0x08008704, "fn_86B4 (uses LRA struct)")
print("\n  fn_86B4 callers = %s" % ["0x%X" % x for x in cg.get(0x080086B4, [])])
f = owner(0x08009378)
print("  caller site 0x08009378 belongs to fn 0x%08X" % (f or 0))
show(max(0, 0x08009360), 0x080093C0, "caller context")

print("\n=== 上溯: 从 0x080086B4 的调用者往上 (最多 5 层) ===")
seen = set(); level = [0x080086B4]
for d in range(5):
    nxt = []
    print("  ---- level %d ----" % d)
    for fn in level:
        if fn in seen: continue
        seen.add(fn)
        cs = cg.get(fn, [])
        tag = "  [ISR %s]" % isr[fn] if fn in isr else ""
        print("    fn 0x%08X%s <- %s" % (fn, tag, ["0x%X" % c for c in cs]))
        for c in cs:
            o = owner(c)
            if o: nxt.append(o)
    level = nxt
    if not level: break

print("\n=== 触觉区域函数是否为 ISR ===")
for s in starts:
    if 0x08008600 <= s < 0x08009800 and s in isr:
        print("   fn 0x%08X  %s" % (s, isr[s]))
