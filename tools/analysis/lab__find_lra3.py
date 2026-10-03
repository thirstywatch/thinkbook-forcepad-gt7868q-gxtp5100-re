# find_lra3.py —— 精确定位 TIM2/LRA 运行时驱动代码
# 关键点：TIM2 基址被缓存在 RAM (0x200040B8)，运行时访问应表现为
#   movw/movt 载入该 RAM 地址 + ldr 取指针 + strh/str 到偏移
# 也直接搜字面量池里的 0x200040B8 / 0x40000000
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True

TARGETS = {
    0x200040B8: "TIM2 缓存指针 (RAM)",
    0x40000000: "TIM2 基址",
    0x40000400: "TIM3 基址",
    0x40010800: "GPIOA",
    0x40010C00: "GPIOB",
    0x40011000: "GPIOC",
    0x20000000: "SRAM 基址",
}

print("=== 1) 字面量池中的目标常量 (4 字节小端) ===")
import struct
for v, nm in TARGETS.items():
    pat = struct.pack("<I", v)
    hits = [m.start() for m in __import__("re").finditer(__import__("re").escape(pat), img)]
    print(f"  {nm:22s} 0x{v:08X}: {len(hits)} 处 {[hex(h) for h in hits[:10]]}")

print("\n=== 2) movw/movt 构造目标地址的代码位置 ===")
insns = list(md.disasm(bytes(img), BASE))
print(f"  反汇编指令总数: {len(insns)}")
resolved = {}
i = 0
while i < len(insns) - 1:
    a, b = insns[i], insns[i + 1]
    if a.mnemonic == "movw" and b.mnemonic == "movt" and a.op_str.startswith("r") and b.op_str.startswith("r"):
        try:
            ra, va = a.op_str.split(", #")
            rb, vb = b.op_str.split(", #")
            if ra == rb:
                full = (int(vb, 16) << 16) | int(va, 16)
                if full in TARGETS or 0x40000000 <= full < 0x40020000 or 0x20004000 <= full < 0x20005000:
                    resolved.setdefault(full, []).append(a.address)
        except ValueError:
            pass
    i += 1
for v, sites in sorted(resolved.items()):
    nm = TARGETS.get(v, "")
    print(f"  0x{v:08X} {nm:22s}: {len(sites)} 处 {[hex(s) for s in sites[:12]]}")

print("\n=== 3) 目标地址附近的代码 (前 3 个位置) ===")
def show(addr, span=14):
    print(f"\n--- 0x{addr:08X} ---")
    n = 0
    started = False
    for ins in insns:
        if ins.address == addr:
            started = True
        if started:
            print(f"  {ins.address:08X}: {ins.bytes.hex():10s} {ins.mnemonic:8s} {ins.op_str}")
            n += 1
            if n >= span:
                break

for v, sites in sorted(resolved.items()):
    for s in sites[:3]:
        show(s)

print("\n=== 4) 所有对 0x200040B8 的引用（含 literal pool 载入）===")
cnt = 0
for idx, ins in enumerate(insns):
    if ins.mnemonic.startswith("ldr") and "pc," in ins.op_str:
        try:
            off = int(ins.op_str.split("#")[-1].rstrip("]"), 0)
            lit_addr = (ins.address + 4) & ~3
            lit_addr += off
            img_off = lit_addr - BASE
            if 0 <= img_off <= len(img) - 4:
                val = struct.unpack_from("<I", img, img_off)[0]
                if val in (0x200040B8, 0x40000000):
                    print(f"  0x{ins.address:08X}: {ins.mnemonic} {ins.op_str}  -> 0x{val:08X}")
                    cnt += 1
                    if cnt > 40:
                        break
        except Exception:
            pass
if cnt == 0:
    print("  (无)")
