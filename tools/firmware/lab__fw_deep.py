# fw_deep.py - 固件深度分析: (1) LRA 触发链上溯 (2) 厂商命令分发器定位
# 只读原厂固件 BIN, 不接触设备
import struct
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
print("image=%d bytes  insns=%d" % (N, len(insns)))

# ---------- 1. 向量表 ----------
sp0, rv0 = struct.unpack_from("<II", img, 0)
print("\n=== vector table ===  SP=0x%08X  Reset=0x%08X" % (sp0, rv0))
f0names = {0:"WWDG",1:"PVD",2:"RTC",3:"FLASH",4:"RCC",5:"EXTI0_1",6:"EXTI2_3",7:"EXTI4_15",
           8:"TSC",9:"DMA1_CH1",10:"DMA1_CH2_3",11:"DMA1_CH4_7",12:"ADC_COMP",13:"TIM1_BRK_UP",
           14:"TIM1_TRG_COM",15:"TIM1_CC",16:"TIM2",17:"TIM3",18:"TIM6_DAC",19:"TIM7",
           20:"TIM14",21:"TIM15",22:"TIM16",23:"TIM17",24:"I2C1",25:"I2C2",26:"SPI1",27:"SPI2",
           28:"USART1",29:"USART2",30:"USART3_8",31:"CEC",32:"CAN"}
for k in range(2, 48):
    v = struct.unpack_from("<I", img, 4*k)[0]
    if v:
        nm = f0names.get(k-16, "irq%d" % (k-16))
        print("  irq%-3d %-12s 0x%08X" % (k-16, nm, v))

# ---------- 2. 调用图 ----------
callers = {}
for i in insns:
    if i.mnemonic in ("bl", "blx") and i.op_str.startswith("#"):
        try:
            t = int(i.op_str[1:], 16)
        except Exception:
            continue
        callers.setdefault(t, []).append(i.address)

def ptr_refs(target):
    pat = struct.pack("<I", target | 1)
    out = []; s = 0
    while True:
        j = img.find(pat, s)
        if j < 0: break
        out.append(BASE + j); s = j + 1
    return out

def show(a0, n=40, title=""):
    print("\n----- %s @0x%08X -----" % (title, a0))
    c = 0
    for i in insns:
        if i.address < a0: continue
        print("  %08X: %-10s %s" % (i.address, i.mnemonic, i.op_str))
        c += 1
        if c >= n: break

# ---------- 3. tbb/tbh 跳转表 (switch) ----------
print("\n=== jump tables (tbb/tbh) ===")
for i in insns:
    if i.mnemonic.startswith("tbb") or i.mnemonic.startswith("tbh"):
        print("  0x%08X  %s %s" % (i.address, i.mnemonic, i.op_str))

# ---------- 4. LRA 链分析 ----------
CHAIN = [
    ("LRA runtime cfg",      0x08009750),
    ("LRA TIM2 init",        0x08008FE8),
    ("PWM hw cfg",           0x08008704),
    ("vib start (upstream)", 0x0800AD80),
    ("waveform cb",          0x0800D6F4),
]
print("\n=== LRA chain callers / ptr refs ===")
for name, a in CHAIN:
    print("  %-22s 0x%08X" % (name, a))
    print("      bl callers : %s" % [hex(x) for x in callers.get(a, [])])
    print("      fptr refs  : %s" % [hex(x) for x in ptr_refs(a)])

# ---------- 5. 从 vib start 上溯 ----------
seen = set()
level = [0x0800AD80]
for depth in range(3):
    nxt = []
    print("\n=== up-level %d ===" % depth)
    for f in level:
        if f in seen: continue
        seen.add(f)
        cs = callers.get(f, []) + [p - 0 for p in ptr_refs(f)]
        print("  fn 0x%08X <- %s" % (f, [hex(c) for c in cs]))
        for c in cs:
            if c < BASE or c >= BASE + N: continue
            show(c - 40, 26, "call site near 0x%08X" % c)
        nxt.extend(cs)
    level = [x for x in nxt if BASE <= x < BASE + N]
    if not level: break

# ---------- 6. 与已知 opcode 的比较 (命令分发器线索) ----------
print("\n=== cmp/sub with known opcode immediates ===")
OPS = {0x0E, 0x10, 0x11, 0x12, 0x13, 0x20, 0x21, 0x03}
hits = []
for i in insns:
    if i.mnemonic in ("cmp", "cmp.w", "subs", "sub", "sub.w", "movs", "mov") and i.op_str.startswith(("r", "#")):
        pass
for i in insns:
    if not i.mnemonic.startswith(("cmp", "sub")):
        continue
    if "#" not in i.op_str: continue
    try:
        v = int(i.op_str.split("#")[1].split(",")[0], 0)
    except Exception:
        continue
    if v in OPS:
        hits.append((i.address, i.mnemonic, i.op_str))
print("  total hits: %d" % len(hits))
for a, m, o in hits[:60]:
    print("    0x%08X  %s %s" % (a, m, o))
