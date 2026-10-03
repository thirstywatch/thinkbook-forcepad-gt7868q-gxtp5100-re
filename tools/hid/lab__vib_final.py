# vib_final.py —— 完整调用图（含字面量池蹦床），先自检再判定
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct, bisect
from collections import defaultdict

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read(); IMG = 0x19ABC; BASE = 0x08000000
img = data[IMG:]; END = BASE + len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
idx = {i.address: k for k, i in enumerate(insns)}

def word_at(va):
    j = va - BASE
    if 0 <= j <= len(img) - 4:
        return struct.unpack_from("<I", img, j)[0]
    return None

def is_thumb(w):
    return w is not None and (w & 1) == 1 and BASE <= (w & ~1) < END

# ---------- 收集所有调用形态 ----------
bl_raw = []      # 直接 bl
lit_calls = []   # (site, target) 字面量池 + bx/blx 蹦床
movwt = {}       # movw/movt 立即数

for i in insns:
    if i.mnemonic in ("bl", "bl.w"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if BASE <= v < END: bl_raw.append((i.address, v))

for j, i in enumerate(insns):
    # ldr rX, [pc, #n]
    if i.mnemonic == "ldr" and "[pc" in i.op_str and i.op_str.startswith("r"):
        reg = i.op_str.split(",")[0].strip()
        try: off = int(i.op_str.split("#")[1].rstrip("]"), 16)
        except (IndexError, ValueError): continue
        litva = ((i.address + 4) & ~3) + off
        # 紧随其后的 bx/blx 同一寄存器 = 间接调用
        nxt = insns[j+1] if j+1 < len(insns) else None
        if nxt and nxt.mnemonic in ("bx", "blx") and nxt.op_str.strip() == reg:
            w = word_at(litva)
            if is_thumb(w):
                lit_calls.append((i.address, w & ~1))
    # movw/movt 相邻对
    if j + 1 < len(insns):
        a, b = insns[j], insns[j+1]
        if a.mnemonic == "movw" and b.mnemonic == "movt":
            ra = a.op_str.split(",")[0].strip(); rb = b.op_str.split(",")[0].strip()
            try:
                va = int(a.op_str.split("#")[1], 16); vb = int(b.op_str.split("#")[1], 16)
            except (IndexError, ValueError): continue
            if ra == rb: movwt[a.address] = ((vb << 16) | va) & 0xFFFFFFFF

# ---------- 函数起点 ----------
starts = set()
for k in range(0, 0x100, 4):
    v = struct.unpack_from("<I", img, k)[0]
    if is_thumb(v): starts.add(v & ~1)
for _, t in bl_raw: starts.add(t)
for _, t in lit_calls: starts.add(t)
for s, v in movwt.items():
    if is_thumb(v): starts.add(v & ~1)
for j, i in enumerate(insns):
    if i.mnemonic == "pop" and "pc" in i.op_str:
        for t in insns[j+1:j+3]:
            if t.mnemonic == "push" and "lr" in t.op_str: starts.add(t.address)
            break
starts = sorted(starts)
def owner(a):
    k = bisect.bisect_right(starts, a) - 1
    return starts[k] if k >= 0 else None

edges = defaultdict(set)
for s, t in bl_raw: edges[owner(s)].add(t)
for s, t in lit_calls: edges[owner(s)].add(t)
n_mw = 0
for s, v in movwt.items():
    if is_thumb(v) and (v & ~1) in starts:
        edges[owner(s)].add(v & ~1); n_mw += 1

print(f"函数起点 {len(starts)} | bl {len(bl_raw)} | 字面量池蹦床 {len(lit_calls)} | movw/movt边 {n_mw}")

def bfs(src, dst, maxn=100000):
    if src == dst: return [src]
    prev = {src: None}; q = [src]; h = 0
    while h < len(q) and h < maxn:
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

RESET = owner(0x08000154)
print(f"\n复位入口函数 = 0x{RESET:08X}")
print(f"复位前 12 条:")
for j in range(idx[0x08000154], idx[0x08000154]+12):
    i = insns[j]; print(f"   {i.address:08X}: {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}")

print("\n" + "="*74)
print("【自检】从复位出发，这些必然被执行的函数可达吗？")
print("="*74)
for nm, t in (("主循环 0x0800AA20", 0x0800AA20), ("I2C ISR 0x08008978", 0x08008978),
              ("TIM3 ISR 0x0800D628", 0x0800D628), ("DMA1 ISR 0x08006B3C", 0x08006B3C),
              ("命令分发器 0x080091C0", 0x080091C0), ("LRA配置 0x08009750", 0x08009750),
              ("播放包装 0x08008628", 0x08008628)):
    p = bfs(RESET, t)
    print(f"  {nm:28s}: {'可达' if p else '不可达'}")
    if p and len(p) <= 12:
        print(f"      {' -> '.join(f'0x{x:08X}' for x in p)}")

print("\n" + "="*74)
print("【自检2】可达函数总数（太小说明图还是残的）")
print("="*74)
seen = set(); q = [RESET]; h = 0
while h < len(q):
    f = q[h]; h += 1
    if f in seen: continue
    seen.add(f)
    for g in edges.get(f, ()):
        if g not in seen: q.append(g)
print(f"  从复位可达 {len(seen)} / {len(starts)} 个函数")
