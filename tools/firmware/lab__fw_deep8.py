# fw_deep8.py - 字节级精确 BL 扫描 -> 重建调用图 -> 追溯震动触发链
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
ins_by_addr = {i.address: i for i in insns}

def decode_bl(off):
    """在 file offset off 处尝试解码 Thumb BL, 返回目标地址或 None"""
    if off + 4 > N: return None
    hw1 = struct.unpack_from("<H", img, off)[0]
    hw2 = struct.unpack_from("<H", img, off + 2)[0]
    if (hw1 & 0xF800) != 0xF000: return None
    if (hw2 & 0xD000) != 0xD000: return None      # BL 要求 hw2 高 4 位 = 1101/1111 组合
    S = (hw1 >> 10) & 1
    imm10 = hw1 & 0x3FF
    J1 = (hw2 >> 13) & 1
    J2 = (hw2 >> 11) & 1
    imm11 = hw2 & 0x7FF
    I1 = (~(J1 ^ S)) & 1
    I2 = (~(J2 ^ S)) & 1
    imm = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if imm & 0x800000: imm -= 0x1000000
    pc = BASE + off + 4
    return pc + imm

# 全图扫描: target -> [sites]
cg = {}
for off in range(0, N - 4, 2):
    t = decode_bl(off)
    if t is None: continue
    if BASE <= t < END:
        cg.setdefault(t, []).append(BASE + off)

print("调用图规模: %d 个被调用目标" % len(cg))

starts = sorted(set([i.address for i in insns if i.mnemonic == "push" and "lr" in i.op_str]))
def owner(a):
    best = None
    for s in starts:
        if s <= a: best = s
        else: break
    return best

def ctx(site, n=14):
    print("      site 0x%08X (fn 0x%08X):" % (site, owner(site) or 0))
    a0 = site - 4 * n
    for i in insns:
        if i.address < a0: continue
        if i.address > site + 6: break
        print("        %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))

print("\n=== 1) 关键函数的真实调用者 (字节级扫描) ===")
for t, nm in ((0x08008628, "start vibration"), (0x08008858, "invoke cb"),
              (0x0800D6F4, "waveform fn"), (0x0800D628, "TIM3 ISR"),
              (0x08009750, "LRA cfg"), (0x08008FE8, "TIM2 init")):
    print("  %-18s 0x%08X <- %s" % (nm, t, ["0x%X" % x for x in cg.get(t, [])]))

print("\n=== 2) 从 start-vibration 向上追溯 ===")
frontier = [(0x08008628, 0)]
seen = set()
for depth in range(4):
    nxt = []
    print("\n  ---- level %d ----" % depth)
    for f, d in frontier:
        if f in seen: continue
        seen.add(f)
        cs = cg.get(f, [])
        print("    fn 0x%08X  callers=%s" % (f, ["0x%X" % c for c in cs]))
        for c in cs:
            ctx(c)
            o = owner(c)
            if o: nxt.append((o, depth + 1))
    frontier = nxt
    if not frontier: break
