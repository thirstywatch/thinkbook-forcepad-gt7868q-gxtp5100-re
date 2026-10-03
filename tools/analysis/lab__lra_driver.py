# lra_driver.py —— 从 TIM2 初始化点反向追出 LRA 驱动函数、调用者、状态机
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
by_addr = {i.address: i for i in insns}
print(f"指令数 {len(insns)}  覆盖 0x{insns[0].address:08X} - 0x{insns[-1].address:08X}")

# 函数边界（push {.., lr} 结尾 pop {.., pc}）的粗略识别
PUSH_LR = ("push", "pop")
starts = []
for i in insns:
    if i.mnemonic in PUSH_LR and ("lr" in i.op_str or "pc" in i.op_str):
        starts.append(i.address)
starts_set = set(starts)

def func_start(addr):
    prev = [s for s in starts if s <= addr]
    return max(prev) if prev else None

def show(addr, count=60, title=""):
    print(f"\n===== {title} 从 0x{addr:08X} =====")
    n = 0
    for i in insns:
        if i.address < addr:
            continue
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")
        n += 1
        if n >= count:
            break

def find_callers(target_addr, limit=20):
    out = []
    for i in insns:
        if i.mnemonic.startswith("bl"):
            try:
                t = int(i.op_str.lstrip("#"), 16)
            except ValueError:
                continue
            if t == target_addr:
                out.append(i.address)
    return out[:limit]

# 1) 找到包含 0x08009026 的函数
fs = func_start(0x08009026)
print(f"\n含 TIM2 初始化的函数起点: 0x{fs:08X}" if fs else "未找到函数起点")
if fs:
    show(fs, 90, "LRA/TIM2 初始化函数")

# 2) 相邻 RAM 变量引用点：0x200040B4 / 0x200040D0 / 0x200040E8 附近
for site, why in ((0x08007E7C, "0x200040B4 唯一引用"),
                  (0x08007E94, "0x200040D0 引用1"),
                  (0x0800864A, "0x200040D0 引用2"),
                  (0x080086F4, "0x200040D0 引用3"),
                  (0x08009754, "0x200040D0 引用4")):
    f2 = func_start(site)
    print(f"\n--- {why} (0x{site:08X}, 所在函数 0x{f2:08X}) ---")
    show(site, 30)

# 3) 谁调用这些函数
print("\n=== 调用者 ===")
targets = [fs] if fs else []
targets += [func_start(s) for s in (0x08007E7C, 0x08007E94, 0x0800864A, 0x080086F4, 0x08009754)]
for t in dict.fromkeys([x for x in targets if x]):
    c = find_callers(t)
    print(f"  函数 0x{t:08X} 的调用者: {[hex(x) for x in c]}")

# 4) 搜 TIM2 寄存器偏移写操作 (CCR1=0x34, ARR=0x2c, CR1=0x00, CCER=0x20, DMAR=0x4c)
print("\n=== 疑似 TIM2 寄存器写入 (str/strh 偏移命中) ===")
offs = {0x34: "CCR1", 0x2c: "ARR", 0x20: "CCER", 0x4c: "DMAR", 0x28: "PSC", 0x0c: "DIER", 0x14: "EGR"}
hits = 0
for i in insns:
    if i.mnemonic in ("str", "strh", "strb") and "#0x" in i.op_str:
        try:
            off = int(i.op_str.split("#")[-1].rstrip("]"), 16)
        except ValueError:
            continue
        if off in offs:
            print(f"  0x{i.address:08X}: {i.mnemonic} {i.op_str:24s} ({offs[off]})")
            hits += 1
            if hits > 60:
                print("  ...(截断)")
                break
print(f"  共 {hits} 处")
