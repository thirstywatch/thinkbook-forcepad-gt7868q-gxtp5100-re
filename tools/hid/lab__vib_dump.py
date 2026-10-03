# vib_dump.py —— 剖析震动相关的关键函数
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct, bisect

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]
END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
byaddr = {i.address: i for i in insns}

def show(a0, n, title):
    print(f"\n{'='*70}\n=== {title}  @0x{a0:08X} ({n} 条) ===\n{'='*70}")
    c = 0
    loop = False
    last = None
    for i in insns:
        if i.address < a0: continue
        # 终止条件：遇到下一个函数的 push {...,lr} 且已经过了至少 20 条
        txt = f"  {i.address:08X}: {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}"
        print(txt)
        c += 1
        if c >= n: break

def callers(t):
    out = []
    for i in insns:
        if i.mnemonic in ("bl", "bl.w"):
            try: v = int(i.op_str.lstrip("#"), 16)
            except ValueError: continue
            if v == t: out.append(i.address)
    return out

# ---- 1. LRA 配置/运行时函数 ----
show(0x08009750, 90, "LRA 配置函数 (含 0x08009784 运行时调用点)")

# ---- 2. 命令分发器 ----
show(0x080091C0, 100, "命令分发器")

# ---- 3. 间接调用器 + 播放包装 ----
show(0x08008628, 40, "播放包装(号称不可达)")
show(0x08008600, 60, "播放包装之前")

# ---- 4. 波形回调 ----
show(0x0800D6F4, 60, "波形回调 0x0800D6F4")

# ---- 5. 初始化链 ----
show(0x0800AD24, 40, "调用 LRA 配置的函数 0x0800AD24")
show(0x08003B68, 50, "0x08003B68 (I2C/前端初始化?)")

# ---- 6. GPIOA 引用修正版 ----
print("\n\n=== 修正版：含 GPIOA(0x40010800) 物化地址的函数 ===")
from collections import defaultdict
starts = set()
for i in range(0, 0x100, 4):
    v = struct.unpack_from("<I", img, i)[0]
    if BASE <= v < END: starts.add(v & ~1)
for i in insns:
    if i.mnemonic in ("bl", "bl.w"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if BASE <= v < END: starts.add(v)
starts = sorted(starts)
def owner(a):
    k = bisect.bisect_right(starts, a) - 1
    return starts[k] if k >= 0 else None
byfn = defaultdict(list)
for i in insns:
    o = owner(i.address)
    if o is not None: byfn[o].append(i)

hits = []
for fn, lst in byfn.items():
    regs = {}
    for i in lst:
        if i.mnemonic == "movw" and i.op_str.startswith("r"):
            try: lo = int(i.op_str.split("#")[1], 16)
            except (IndexError, ValueError): continue
            regs[i.op_str.split(",")[0]] = lo
        elif i.mnemonic == "movt" and i.op_str.startswith("r"):
            r = i.op_str.split(",")[0]
            try: hi = int(i.op_str.split("#")[1], 16)
            except (IndexError, ValueError): continue
            if r in regs and ((hi << 16) | regs[r]) == 0x40010800:
                hits.append((fn, i.address))
for fn, site in sorted(hits):
    print(f"  0x{fn:08X}  (物化点 0x{site:08X})")
print(f"  共 {len(set(f for f, _ in hits))} 个函数")
