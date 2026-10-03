# lra_chain2.py —— 追 PWM 配置函数的调用链，找"震动触发"上游
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
print(f"指令 {len(insns)} 覆盖到 0x{insns[-1].address:08X} (镜像 0x{BASE+len(img):08X})")

def show(addr, count=48, title="", stop_at_ret=True):
    print(f"\n===== {title} @0x{addr:08X} =====")
    n = 0
    for i in insns:
        if i.address < addr:
            continue
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
        n += 1
        if n >= count:
            break

def callers(target, limit=25):
    out = []
    for i in insns:
        if i.mnemonic.startswith("bl"):
            try:
                t = int(i.op_str.lstrip("#"), 16)
            except ValueError:
                continue
            if t == target:
                out.append(i.address)
    return out[:limit]

def func_start(addr):
    best = None
    for i in insns:
        if i.address > addr:
            break
        if i.mnemonic == "push" and ("lr" in i.op_str):
            best = i.address
    return best

# PWM 配置函数
show(0x08008704, 70, "PWM 配置函数 (被 LRA 初始化调用)")

print("\n=== 调用链 ===")
level1 = callers(0x08008704)
print(f"  0x08008704 的调用者: {[hex(x) for x in level1]}")
for c in level1:
    level2 = callers(c)
    print(f"  0x{c:08X} 的调用者: {[hex(x) for x in level2]}")
    for c2 in level2[:4]:
        level3 = callers(c2)
        print(f"      0x{c2:08X} 的调用者: {[hex(x) for x in level3]}")

# 也看模块结构 B 的回调
print("\n=== 回调 0x08005DE1 (模块 B 的 handler) ===")
show(0x08005DE1, 40, "handler B")
