# fw_deep5.py - 提取全部 movw+movt 常量: 外设基址 / SRAM 缓冲区 / 代码指针
import struct, collections
from capstone import *

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
OFF = 0x19ABC
img = data[OFF:]
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

mats = []
pending = {}
for ins in insns:
    try:
        if ins.mnemonic.startswith("movw") and "#" in ins.op_str:
            reg = ins.op_str.split(",")[0].strip()
            pending[reg] = (int(ins.op_str.split("#")[1], 0), ins.address)
        elif ins.mnemonic.startswith("movt") and "#" in ins.op_str:
            reg = ins.op_str.split(",")[0].strip()
            if reg in pending:
                lo, at = pending.pop(reg)
                mats.append((at, (int(ins.op_str.split("#")[1], 0) << 16) | (lo & 0xFFFF)))
    except Exception:
        pass

REG = {
    0x40000000: "TIM2", 0x40000400: "TIM3", 0x40005400: "I2C1", 0x40013800: "USART1",
    0x40021000: "RCC", 0x40022000: "FLASH", 0x40020000: "?20000", 0x40010000: "?10000",
    0x40015800: "?15800", 0x40012400: "ADC", 0x40012C00: "TIM1", 0x40002000: "?2000",
    0x40003800: "?3800", 0x40004800: "?4800", 0x40006C00: "?6C00",
}
def label(v):
    if v in REG: return REG[v]
    if 0x40000000 <= v < 0x40040000: return "PERIPH+0x%X" % (v - 0x40000000)
    if 0x20000000 <= v < 0x20010000: return "SRAM+0x%X" % (v - 0x20000000)
    if 0x08000000 <= v < 0x08010000: return "CODE"
    return "0x%08X" % v

print("=== 外设基址引用 (movw/movt) ===")
byval = collections.defaultdict(list)
for at, v in mats:
    byval[v].append(at)
for v in sorted(byval):
    if 0x40000000 <= v < 0x40040000:
        print("  %-14s 0x%08X  sites=%s" % (label(v), v, ["0x%X" % a for a in byval[v][:8]]))

print("\n=== TIM2 / TIM3 引用点所属函数 ===")
for v, nm in ((0x40000000, "TIM2"), (0x40000400, "TIM3")):
    for a in byval.get(v, []):
        f = owner(a)
        print("  %s site=0x%08X  fn=0x%08X" % (nm, a, f if f else 0))

print("\n=== SRAM 引用最多的地址 (候选缓冲区) ===")
sram = [(v, byval[v]) for v in byval if 0x20000000 <= v < 0x20010000]
sram.sort(key=lambda kv: -len(kv[1]))
for v, ats in sram[:30]:
    print("  %-16s 0x%08X  refs=%2d  sites=%s" % (label(v), v, len(ats), ["0x%X" % a for a in ats[:6]]))

print("\n=== 代码指针 (回调注册) ===")
for v in sorted(byval):
    if 0x08000000 <= v < 0x08010000:
        print("  -> 0x%08X  at %s" % (v, ["0x%X" % a for a in byval[v][:6]]))
