# fw_deep2.py - 找函数边界 / 追 movw+movt 构造的指针 / 展开 tbb-tbh 跳转表
import struct
from capstone import *

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
OFF = 0x19ABC
img = data[OFF:]
BASE = 0x08000000
N = len(img)
END = BASE + N

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
byaddr = {i.address: i for i in insns}
order = [i.address for i in insns]

def enclosing(a):
    """往前找最近的一个 push{...,lr} 作为函数入口"""
    best = None
    for i in insns:
        if i.address > a: break
        if i.mnemonic == "push" and "lr" in i.op_str:
            best = i.address
    return best

def callers(t):
    o = []
    for i in insns:
        if i.mnemonic in ("bl", "blx") and i.op_str.startswith("#"):
            try:
                if int(i.op_str[1:], 16) == t: o.append(i.address)
            except Exception: pass
    return o

def show(a0, n=40, title=""):
    print("\n----- %s @0x%08X -----" % (title, a0))
    c = 0
    for i in insns:
        if i.address < a0: continue
        print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))
        c += 1
        if c >= n: break

print("=== A) 震动启动函数: 0x0800AD7C 所在函数 ===")
fA = enclosing(0x0800AD7C)
print("  function start = 0x%08X" % (fA if fA else -1))
if fA:
    print("  callers of it  = %s" % [hex(x) for x in callers(fA)])
    for c in callers(fA):
        show(enclosing(c), 30, "caller fn (site 0x%08X)" % c)
    show(fA, 70, "vibration start fn")

print("\n=== B) movw+movt 构造的地址 (回调注册候选) ===")
mats = []
i = 0
pending = {}
for ins in insns:
    if ins.mnemonic.startswith("movw") and "#" in ins.op_str:
        try:
            reg = ins.op_str.split(",")[0].strip()
            v = int(ins.op_str.split("#")[1], 0)
            pending[reg] = (v, ins.address)
        except Exception: pass
    elif ins.mnemonic.startswith("movt") and "#" in ins.op_str:
        try:
            reg = ins.op_str.split(",")[0].strip()
            v = int(ins.op_str.split("#")[1], 0)
            if reg in pending:
                lo, at = pending.pop(reg)
                full = (v << 16) | (lo & 0xFFFF)
                if BASE <= full < END and (full & 1):
                    mats.append((at, full))
        except Exception: pass
mats.sort()
print("  total materialized code ptrs: %d" % len(mats))
for at, v in mats:
    print("    0x%08X -> 0x%08X" % (at, v))

print("\n=== C) tbb/tbh 跳转表展开 ===")
TBL = [(0x080012CC, "tbb"), (0x08008D9C, "tbb"), (0x0800B3D6, "tbb"),
       (0x0800B5C6, "tbh"), (0x0800B896, "tbb"), (0x0800B920, "tbb"), (0x0800B96A, "tbb")]
for a, kind in TBL:
    ins = byaddr.get(a)
    if not ins: continue
    # 表基址 = 指令之后, 2 字节对齐
    tb = a + ins.size
    if tb % 2: tb += 1
    fo = tb - BASE
    print("\n--- %s @0x%08X (table @0x%08X, %s) ---" % (kind, a, tb, ins.op_str))
    if kind == "tbb":
        ents = img[fo:fo + 32]
        for k, e in enumerate(ents):
            tgt = tb + 2 * e
            print("    case %2d (0x%02X) -> 0x%08X" % (k, e, tgt))
    else:
        for k in range(24):
            e = struct.unpack_from("<H", img, fo + 2 * k)[0]
            tgt = tb + 2 * e
            print("    case %2d (0x%04X) -> 0x%08X" % (k, e, tgt))
    show(a - 24, 30, "context around %s" % kind)
