# fw_deep16.py - 修正后: 魔数帧构造点 + GPIO 引用 + 发帧调用者
from capstone import *
import struct

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

# 物化常量
mats = []
pending = {}
for ins in insns:
    o = ins.op_str
    try:
        if ins.mnemonic.startswith("movw") and "#" in o:
            r = o.split(",")[0].strip(); pending[r] = (int(o.split("#")[1], 0), ins.address)
        elif ins.mnemonic.startswith("movt") and "#" in o:
            r = o.split(",")[0].strip()
            if r in pending:
                lo, at = pending.pop(r)
                mats.append((at, (int(o.split("#")[1], 0) << 16) | (lo & 0xFFFF)))
    except Exception: pass

print("=== 1) 魔数字节写入点 (修正) ===")
MAG = {"0xa2","0xa5","0x5a","0x2a","0xa1","0x1a","0xc3","0x3c","0x5c","0xc5","0x0e","0x20"}
cnt = 0
for k, i in enumerate(insns):
    if not i.mnemonic.startswith("mov"): continue
    o = i.op_str
    if "," not in o: continue
    imm = o.split(",")[-1].strip().lstrip("#").lower()
    if imm not in MAG: continue
    if not any(t.mnemonic.startswith("str") for t in insns[k+1:k+3]): continue
    print("   0x%08X  fn=0x%08X  %s %s" % (i.address, owner(i.address) or 0, i.mnemonic, o))
    cnt += 1
    if cnt >= 25: break
print("   shown=%d" % cnt)

print("\n=== 2) GPIO 端口引用 (物化地址) ===")
gp = {}
for at, v in mats:
    if v in (0x40010800, 0x40010C00, 0x40011000, 0x40011400, 0x40011800, 0x40011C00):
        gp.setdefault(owner(at), []).append((at, v))
for f, lst in sorted(gp.items(), key=lambda kv: -len(kv[1])):
    print("   fn 0x%08X  refs=%d  %s" % (f or 0, len(lst), ["0x%X:0x%X" % (a, v) for a, v in lst[:8]]))

print("\n=== 3) 发帧函数 0x08008868 的调用者及其上下文 ===")
def decode_bl(off):
    if off + 4 > N: return None
    h1 = struct.unpack_from("<H", img, off)[0]; h2 = struct.unpack_from("<H", img, off + 2)[0]
    if (h1 & 0xF800) != 0xF000 or (h2 & 0xD000) != 0xD000: return None
    S = (h1 >> 10) & 1; i10 = h1 & 0x3FF; J1 = (h2 >> 13) & 1; J2 = (h2 >> 11) & 1; i11 = h2 & 0x7FF
    I1 = (~(J1 ^ S)) & 1; I2 = (~(J2 ^ S)) & 1
    imm = (S << 24) | (I1 << 23) | (I2 << 22) | (i10 << 12) | (i11 << 1)
    if imm & 0x1000000: imm -= 0x2000000
    return BASE + off + 4 + imm
cg = {}
for off in range(0, N - 4, 2):
    t = decode_bl(off)
    if t is not None and BASE <= t < BASE + N: cg.setdefault(t, []).append(BASE + off)

for tgt in (0x08008868, 0x08008858, 0x080088C0):
    cs = cg.get(tgt, [])
    print("   0x%08X <- %s" % (tgt, ["0x%X(fn 0x%X)" % (c, owner(c) or 0) for c in cs]))
print("\n   0x0800968A 附近:")
for i in insns:
    if 0x08009670 <= i.address <= 0x080096C0:
        print("      %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))
