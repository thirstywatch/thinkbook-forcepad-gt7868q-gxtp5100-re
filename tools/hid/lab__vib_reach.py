# vib_reach.py —— 严格的调用图可达性分析
# 问题：LRA 驱动链（震动）从 I2C 命令分发器/中断是否可达？
# 这决定"固件层面是否存在主机可触发的震动路径"。
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]
END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
print(f"镜像 {len(img)} 字节, 反汇编 {len(insns)} 条指令, 范围 0x{BASE:08X}-0x{END:08X}")

# ---------- 1. 函数起点集合 ----------
starts = set()

# 1a. 向量表：镜像开头 0x100 字节，每条 u32 = 函数地址|1
for i in range(0, 0x100, 4):
    v = struct.unpack_from("<I", img, i)[0]
    if BASE <= v < END:
        starts.add(v & ~1)

# 1b. 所有 bl 目标
bl_edges_raw = []   # (site, target)
for i in insns:
    if i.mnemonic in ("bl", "bl.w"):
        try:
            v = int(i.op_str.lstrip("#"), 16)
        except ValueError:
            continue
        if BASE <= v < END:
            bl_edges_raw.append((i.address, v))
            starts.add(v)

# ---------- 1d. movw/movt 相邻对（先算出来，其目标也算函数起点） ----------
movwt = {}
i = 0
while i < len(insns) - 1:
    a, b = insns[i], insns[i + 1]
    if a.mnemonic == "movw" and b.mnemonic == "movt" and "," in a.op_str and "," in b.op_str:
        ra = a.op_str.split(",")[0].strip()
        rb = b.op_str.split(",")[0].strip()
        try:
            va = int(a.op_str.split("#")[1], 16)
            vb = int(b.op_str.split("#")[1], 16)
        except (IndexError, ValueError):
            i += 1; continue
        if ra == rb:
            movwt[a.address] = ((vb << 16) | va) & 0xFFFFFFFF
    i += 1

# 函数指针目标也纳入起点集合
for site, val in movwt.items():
    if (val & 1) == 1 and BASE <= (val & ~1) < END:
        starts.add(val & ~1)

# 字面量池里的函数指针目标
for i2 in insns:
    if i2.mnemonic == "ldr" and "[pc" in i2.op_str:
        try:
            off = int(i2.op_str.split("#")[1].rstrip("]"), 16)
        except (IndexError, ValueError):
            continue
        lit = ((i2.address + 4) & ~3) + off
        j = lit - BASE
        if 0 <= j <= len(img) - 4:
            v = struct.unpack_from("<I", img, j)[0]
            if (v & 1) == 1 and BASE <= (v & ~1) < END:
                starts.add(v & ~1)

starts = sorted(starts)
print(f"函数起点 {len(starts)} 个 (向量表 + bl 目标 + 函数指针目标；不含函数内部嵌套 push)")

# ---------- 2. 每条指令归属函数 ----------
import bisect
def owner(addr):
    k = bisect.bisect_right(starts, addr) - 1
    return starts[k] if k >= 0 else None

# ---------- 3. 直接边 ----------
edges = {}   # fn -> set(callee)
def add_edge(a, b):
    if a is None or b is None: return
    edges.setdefault(a, set()).add(b)

for site, tgt in bl_edges_raw:
    add_edge(owner(site), tgt)

# ---------- 4. 间接边：movw/movt 构造的函数指针 ----------
n_ptr = 0
for site, val in movwt.items():
    if (val & 1) == 1 and BASE <= (val & ~1) < END:
        tgt = val & ~1
        if tgt in starts:
            add_edge(owner(site), tgt)
            n_ptr += 1
print(f"movw/movt 对 {len(movwt)} 个, 其中构成函数指针的间接边 {n_ptr} 条")

# 4b. 字面量池里的函数指针（ldr rX, [pc, #n] 指向的 word）
litptr = 0
for i in insns:
    if i.mnemonic == "ldr" and "[pc" in i.op_str:
        try:
            off = int(i.op_str.split("#")[1].rstrip("]"), 16)
        except (IndexError, ValueError):
            continue
        # Thumb 下 PC = 当前地址 + 4，且字对齐
        lit = (i.address + 4) & ~3
        lit += off
        j = lit - BASE
        if 0 <= j <= len(img) - 4:
            v = struct.unpack_from("<I", img, j)[0]
            if (v & 1) == 1 and BASE <= (v & ~1) < END and (v & ~1) in starts:
                add_edge(owner(i.address), v & ~1)
                litptr += 1
print(f"字面量池函数指针 {litptr} 条")

# 4c. 数据段中的函数指针表：扫描整个镜像里的 Thumb 指针，找出它们所在位置
def ptr_sites(fn):
    pat = struct.pack("<I", fn | 1)
    out, s = [], 0
    while True:
        j = img.find(pat, s)
        if j < 0: break
        out.append(BASE + j); s = j + 1
    return out

# ---------- 5. 可达性 BFS ----------
def reach(seed):
    seen = set()
    stack = [seed]
    while stack:
        f = stack.pop()
        if f in seen: continue
        seen.add(f)
        for g in edges.get(f, ()):
            if g not in seen:
                stack.append(g)
    return seen

SEEDS = {
    "I2C1_EV ISR         0x08008978": 0x08008978,
    "I2C1_ER ISR         0x0800894C": 0x0800894C,
    "TIM3 ISR (波形)     0x0800D628": 0x0800D628,
    "DMA1_CH1 ISR        0x08006B3C": 0x08006B3C,
    "命令分发器          0x080091C0": 0x080091C0,
    "主循环              0x0800AA20": 0x0800AA20,
    "复位入口            0x08000155": 0x08000154,
}

# 关键 LRA 函数
LRA = {
    "LRA TIM3 运行时配置 0x08009750": 0x08009750,
    "LRA 运行时调用点所在函数": None,   # 下面算
    "播放包装(号称不可达) 0x08008628": 0x08008628,
    "波形回调 0x0800D6F4": 0x0800D6F4,
    "PWM 硬件配置 0x08008704": 0x08008704,
    "TIM2 初始化 0x08008FE8": 0x08008FE8,
    "间接调用器 0x08008858": 0x08008858,
    "发帧函数 0x08008868": 0x08008868,
}
LRA["LRA 运行时调用点所在函数"] = owner(0x08009784)

print("\n=== 关键函数归属 ===")
for nm, fn in LRA.items():
    print(f"  {nm} -> owner=0x{fn:08X}" if fn else f"  {nm} -> 未归属")

print("\n=== 各入口的调用图规模 ===")
reachsets = {}
for nm, a in SEEDS.items():
    r = reach(owner(a) or a)
    reachsets[nm] = r
    print(f"  {nm:38s} 可达函数 {len(r):5d} 个")

print("\n=== ★ 关键判定：LRA 链是否落在任何入口的可达集里 ===")
for nm, fn in LRA.items():
    if fn is None:
        print(f"  {nm}: 无法归属"); continue
    hits = [snm for snm, r in reachsets.items() if fn in r]
    ptr = ptr_sites(fn)
    print(f"  {nm}")
    print(f"     直接调用者: {[hex(owner(x)) for x in []]}")  # 占位
    print(f"     可达自: {hits if hits else '【不可达】'}")
    print(f"     作为 Thumb 指针出现于: {[hex(x) for x in ptr[:6]]}")

print("\n=== 谁直接调用 LRA 运行时函数 / 播放包装 ===")
for nm, fn in (("LRA运行时", LRA["LRA 运行时调用点所在函数"]),
               ("播放包装", 0x08008628),
               ("间接调用器", 0x08008858)):
    cs = sorted({owner(s) for s, t in bl_edges_raw if t == fn})
    print(f"  {nm} 0x{fn:08X}: 调用者函数 = {[hex(c) for c in cs] if cs else '【无直接调用者】'}")

print("\n=== 命令分发器 0x080091C0 里出现的 movw/movt 函数指针 ===")
d = owner(0x080091C0)
if d:
    for site, val in sorted(movwt.items()):
        if owner(site) == d and (val & 1) == 1 and BASE <= (val & ~1) < END:
            print(f"  0x{site:08X}: -> 0x{val & ~1:08X}")

print("\n=== 从命令分发器可达的、写 GPIOA(0x40010800) 的函数 ===")
from collections import defaultdict
byfn = defaultdict(list)
for i in insns:
    o = owner(i.address)
    if o is not None:
        byfn[o].append(i)

gpio_fns = []
for fn, lst in byfn.items():
    regs = {}
    has = False
    for i in lst:
        if i.mnemonic == "movw" and i.op_str.startswith("r") and "#0x0800" in i.op_str:
            regs[i.op_str.split(",")[0]] = 0x0800
        elif i.mnemonic == "movt" and i.op_str.startswith("r"):
            r = i.op_str.split(",")[0]
            try: hi = int(i.op_str.split("#")[1], 16)
            except (IndexError, ValueError): continue
            if r in regs and ((hi << 16) | regs[r]) == 0x40010800:
                has = True
    if has:
        gpio_fns.append(fn)

r = reachsets["命令分发器          0x080091C0"]
print(f"  全镜像含 GPIOA 引用的函数 {len(gpio_fns)} 个")
for fn in sorted(gpio_fns):
    mark = "★可达" if fn in r else "不可达"
    print(f"    0x{fn:08X}  {mark}")

print("\n=== 反向：谁能到达 LRA 运行时函数（完整反向路径） ===")
rev = defaultdict(set)
for a, bs in edges.items():
    for b in bs:
        rev[b].add(a)
target = LRA["LRA 运行时调用点所在函数"]
if target:
    seen = set()
    stack = [target]
    while stack:
        f = stack.pop()
        if f in seen: continue
        seen.add(f)
        for g in rev.get(f, ()):
            if g not in seen: stack.append(g)
    print(f"  能到达 0x{target:08X} 的函数共 {len(seen)} 个")
    # 反向可达集里，哪些落在各入口可达集内 => 存在通路
    for snm, rs in reachsets.items():
        inter = seen & rs
        print(f"     {snm:38s} 交集 {len(inter)} 个 {[hex(x) for x in list(inter)[:5]]}")
    # 直接调用者链
    print(f"  直接调用者: {[hex(x) for x in rev.get(target, ())]}")
    for c in list(rev.get(target, ()))[:6]:
        print(f"     0x{c:08X} <- {[hex(x) for x in rev.get(c, ())]}")
