# vib_reach2.py —— 修正函数边界后的可达性（关键：pop{...,pc} 之后的 push{...,lr} 是函数起点）
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct, bisect
from collections import defaultdict

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read(); IMG = 0x19ABC; BASE = 0x08000000
img = data[IMG:]; END = BASE + len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
idx = {i.address: k for k, i in enumerate(insns)}

# ---------- 函数起点（三路合并） ----------
starts = set()
# (a) 向量表
for k in range(0, 0x100, 4):
    v = struct.unpack_from("<I", img, k)[0]
    if BASE <= v < END: starts.add(v & ~1)
# (b) bl 目标
bl_raw = []
for i in insns:
    if i.mnemonic in ("bl", "bl.w"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if BASE <= v < END:
            bl_raw.append((i.address, v)); starts.add(v)
# (c) 函数尾 pop{...,pc} 之后（跳过填充）的 push{...,lr}
PAD = {"movs r0, r0", "nop", "nop.w"}
for j, i in enumerate(insns):
    if i.mnemonic == "pop" and "pc" in i.op_str:
        for t in insns[j+1:j+4]:
            if t.mnemonic == "push" and "lr" in t.op_str:
                starts.add(t.address); break
            if (f"{t.mnemonic} {t.op_str}") in PAD or t.mnemonic == "nop":
                continue
            break
# (d) movw/movt + 字面量池函数指针
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
print(f"函数起点 {len(starts)} 个；0x08008628 是否在集合内: {0x08008628 in starts}")

edges = defaultdict(set)
for s, t in bl_raw: edges[owner(s)].add(t)
n_ind = 0
for s, v in movwt.items():
    if (v & 1) and BASE <= (v & ~1) < END and (v & ~1) in starts:
        edges[owner(s)].add(v & ~1); n_ind += 1
print(f"bl 边 {len(bl_raw)} 条, 间接边 {n_ind} 条")

TARGETS = {
    "★播放包装 0x08008628":        0x08008628,
    "  间接调用器 0x08008858":      0x08008858,
    "  波形回调 0x0800D6F4":        0x0800D6F4,
    "  LRA配置 0x08009750":         0x08009750,
    "  PWM配置 0x08008704":         0x08008704,
    "  TIM3读写A 0x0800BD44":       0x0800BD44,
    "  TIM3读写B 0x0800BD30":       0x0800BD30,
}
ENTRIES = {
    "命令分发器 0x080091C0": 0x080091C0,
    "DMA1_CH1 ISR 0x08006B3C": 0x08006B3C,
    "I2C1_EV ISR 0x08008978": 0x08008978,
    "I2C1_ER ISR 0x0800894C": 0x0800894C,
    "TIM3 ISR 0x0800D628": 0x0800D628,
    "主循环 0x0800AA20": 0x0800AA20,
    "复位 0x08000154": 0x08000154,
}

def bfs(src, dst):
    if src == dst: return [src]
    prev = {src: None}; q = [src]; h = 0
    while h < len(q):
        f = q[h]; h += 1
        for g in edges.get(f, ()):
            if g not in prev:
                prev[g] = f
                if g == dst:
                    p = [g]
                    while prev[p[-1]] is not None: p.append(prev[p[-1]])
                    return list(reversed(p))
                q.append(g)
    return None

print("\n" + "="*74)
print("=== 修正后的可达性 ===")
print("="*74)
for enm, ea in ENTRIES.items():
    es = owner(ea) or ea
    print(f"\n--- {enm} (0x{es:08X}) ---")
    for tnm, ta in TARGETS.items():
        p = bfs(es, ta)
        if p:
            print(f"  {tnm}: 可达 ({len(p)} 跳)")
            print(f"       {' -> '.join(f'0x{x:08X}' for x in p)}")
        else:
            print(f"  {tnm}: 【不可达】")

# ---- 播放包装的直接/间接引用 ----
print("\n" + "="*74)
print("=== 0x08008628(播放包装) 的所有引用方式 ===")
print("="*74)
direct = sorted({owner(s) for s, t in bl_raw if t == 0x08008628})
print(f"  bl 调用者: {[hex(x) for x in direct] if direct else '【无】'}")
for nm, val in (("movw/movt", 0x08008628), ("movw/movt|1", 0x08008629)):
    sites = [hex(s) for s, v in movwt.items() if v == val]
    print(f"  {nm} 立即数出现于: {sites if sites else '【无】'}")
for val in (0x08008628, 0x08008629):
    pat = struct.pack("<I", val); out = []; s0 = 0
    while True:
        j = img.find(pat, s0)
        if j < 0: break
        out.append(BASE + j); s0 = j + 1
    print(f"  字面量池 word 0x{val:08X} 出现于: {[hex(x) for x in out] if out else '【无】'}")

# ---- 谁调用 TIM3 读写 A/B ----
for nm, t in (("0x0800BD44", 0x0800BD44), ("0x0800BD30", 0x0800BD30)):
    cs = sorted({owner(s) for s, x in bl_raw if x == t})
    print(f"\n  调用 {nm} 的函数: {[hex(x) for x in cs] if cs else '【无】'}")
