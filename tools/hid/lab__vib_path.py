# vib_path.py —— 从主机入口到"播放震动"的路径追踪
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct, bisect
from collections import defaultdict

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC; BASE = 0x08000000
img = data[IMG:]; END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
idx = {i.address: k for k, i in enumerate(insns)}

# ---- 函数起点 ----
starts = set()
for k in range(0, 0x100, 4):
    v = struct.unpack_from("<I", img, k)[0]
    if BASE <= v < END: starts.add(v & ~1)
bl_raw = []
for i in insns:
    if i.mnemonic in ("bl", "bl.w"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if BASE <= v < END:
            bl_raw.append((i.address, v)); starts.add(v)
# movw/movt 函数指针
movwt = {}
for a, b in zip(insns, insns[1:]):
    if a.mnemonic == "movw" and b.mnemonic == "movt":
        ra = a.op_str.split(",")[0].strip(); rb = b.op_str.split(",")[0].strip()
        try:
            va = int(a.op_str.split("#")[1], 16); vb = int(b.op_str.split("#")[1], 16)
        except (IndexError, ValueError): continue
        if ra == rb: movwt[a.address] = ((vb << 16) | va) & 0xFFFFFFFF
for s, v in movwt.items():
    if (v & 1) and BASE <= (v & ~1) < END: starts.add(v & ~1)
# 字面量池指针
for i in insns:
    if i.mnemonic == "ldr" and "[pc" in i.op_str:
        try: off = int(i.op_str.split("#")[1].rstrip("]"), 16)
        except (IndexError, ValueError): continue
        j = (((i.address + 4) & ~3) + off) - BASE
        if 0 <= j <= len(img) - 4:
            v = struct.unpack_from("<I", img, j)[0]
            if (v & 1) and BASE <= (v & ~1) < END: starts.add(v & ~1)
starts = sorted(starts)
def owner(a):
    k = bisect.bisect_right(starts, a) - 1
    return starts[k] if k >= 0 else None

# ---- 边 ----
edges = defaultdict(set)
for s, t in bl_raw: edges[owner(s)].add(t)
n_ind = 0
for s, v in movwt.items():
    if (v & 1) and BASE <= (v & ~1) < END and (v & ~1) in starts:
        edges[owner(s)].add(v & ~1); n_ind += 1
print(f"函数 {len(starts)} 个, bl 边 {len(bl_raw)} 条, 间接边 {n_ind} 条")

PLAY_SITE = 0x0800864A
IND_CALLER = 0x08008858
WAVE_CB   = 0x0800D6F4
LRA_CFG   = 0x08009750
PWM_CFG   = 0x08008704

# ---- 播放函数的真实起点：从 0x0800864A 向前找最近的、在 starts 里的地址 ----
cands = [s for s in starts if s <= PLAY_SITE]
play_fn = cands[-1]
print(f"\n播放站点 0x{PLAY_SITE:08X} 所在函数 = 0x{play_fn:08X}")
print(f"  该函数是否是 starts 成员(有 bl 指向它)? {play_fn in [t for _, t in bl_raw]}")
print(f"  owner(0x0800865C)=0x{owner(0x0800865C):08X}  (下一个函数的起点)")

# 列出该函数头 8 条
k = idx[play_fn]
print(f"  --- 0x{play_fn:08X} 头部 ---")
for j in range(k, min(k + 10, len(insns))):
    i = insns[j]
    print(f"     {i.address:08X}: {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}")

# ---- 谁调用 play_fn ----
rev = defaultdict(set)
for a, bs in edges.items():
    for b in bs: rev[b].add(a)
print(f"\n=== 调用 0x{play_fn:08X} 的函数 ===")
direct = sorted({owner(s) for s, t in bl_raw if t == play_fn})
print(f"  bl 调用者: {[hex(x) for x in direct]}")
print(f"  图内前驱: {[hex(x) for x in rev.get(play_fn, ())]}")
ptr = []
pat = struct.pack("<I", play_fn | 1); s0 = 0
while True:
    j = img.find(pat, s0)
    if j < 0: break
    ptr.append(BASE + j); s0 = j + 1
print(f"  作为 Thumb 指针出现于: {[hex(x) for x in ptr]}")

# ---- 可达性 + 路径 ----
ENTRIES = {
    "I2C1_EV ISR     0x08008978": 0x08008978,
    "I2C1_ER ISR     0x0800894C": 0x0800894C,
    "DMA1_CH1 ISR    0x08006B3C": 0x08006B3C,
    "TIM3 ISR        0x0800D628": 0x0800D628,
    "命令分发器      0x080091C0": 0x080091C0,
    "主循环          0x0800AA20": 0x0800AA20,
    "复位            0x08000154": 0x08000154,
}
TARGETS = {"播放函数": play_fn, "间接调用器": IND_CALLER, "波形回调": WAVE_CB,
           "LRA配置": LRA_CFG, "PWM配置": PWM_CFG}

def bfs_path(src, dst, limit=200000):
    if src == dst: return [src]
    prev = {src: None}
    q = [src]; head = 0
    while head < len(q):
        f = q[head]; head += 1
        if head > limit: break
        for g in edges.get(f, ()):
            if g not in prev:
                prev[g] = f
                if g == dst:
                    path = [g]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])
                    return list(reversed(path))
                q.append(g)
    return None

print("\n" + "="*72)
print("=== 从各入口到各目标的路径 ===")
print("="*72)
for enm, ea in ENTRIES.items():
    es = owner(ea) or ea
    print(f"\n--- {enm} (起点函数 0x{es:08X}) ---")
    for tnm, ta in TARGETS.items():
        p = bfs_path(es, ta)
        if p:
            print(f"   ★ {tnm} 0x{ta:08X}: 可达!  路径长度 {len(p)}")
            print(f"        {' -> '.join(f'0x{x:08X}' for x in p)}")
        else:
            print(f"     {tnm} 0x{ta:08X}: 不可达")
