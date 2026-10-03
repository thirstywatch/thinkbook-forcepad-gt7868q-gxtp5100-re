# vib_tim3.py —— 所有操作 TIM3(0x40000400) 的站点 + 修正复位入口后的可达性
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
    return struct.unpack_from("<I", img, j)[0] if 0 <= j <= len(img) - 4 else None
def is_thumb(w):
    return w is not None and (w & 1) == 1 and BASE <= (w & ~1) < END

bl_raw, lit_calls, movwt = [], [], {}
for i in insns:
    if i.mnemonic in ("bl", "bl.w"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if BASE <= v < END: bl_raw.append((i.address, v))
for j, i in enumerate(insns):
    if i.mnemonic == "ldr" and "[pc" in i.op_str and i.op_str.startswith("r"):
        reg = i.op_str.split(",")[0].strip()
        try: off = int(i.op_str.split("#")[1].rstrip("]"), 16)
        except (IndexError, ValueError): continue
        nxt = insns[j+1] if j+1 < len(insns) else None
        if nxt and nxt.mnemonic in ("bx", "blx") and nxt.op_str.strip() == reg:
            w = word_at(((i.address + 4) & ~3) + off)
            if is_thumb(w): lit_calls.append((i.address, w & ~1))
    if j + 1 < len(insns):
        a, b = insns[j], insns[j+1]
        if a.mnemonic == "movw" and b.mnemonic == "movt":
            ra = a.op_str.split(",")[0].strip(); rb = b.op_str.split(",")[0].strip()
            try:
                va = int(a.op_str.split("#")[1], 16); vb = int(b.op_str.split("#")[1], 16)
            except (IndexError, ValueError): continue
            if ra == rb: movwt[a.address] = ((vb << 16) | va) & 0xFFFFFFFF

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
for s, v in movwt.items():
    if is_thumb(v) and (v & ~1) in starts: edges[owner(s)].add(v & ~1)

RESET = 0x08005164
print(f"复位入口 = 0x{RESET:08X}  (向量表[1])")
seen = set(); q = [RESET]; h = 0
while h < len(q):
    f = q[h]; h += 1
    if f in seen: continue
    seen.add(f)
    for g in edges.get(f, ()):
        if g not in seen: q.append(g)
print(f"从复位可达 {len(seen)} / {len(starts)} 个函数\n")

def reachable(t):
    if t in seen: return True
    return any(bfs_target(t) for _ in [0]) if False else False

print("="*74)
print("【自检】必然被执行的函数，从复位可达吗？")
print("="*74)
for nm, t in (("主循环 0x0800AA20", 0x0800AA20), ("I2C1_EV ISR 0x08008978", 0x08008978),
              ("TIM3 ISR 0x0800D628", 0x0800D628), ("DMA1 ISR 0x08006B3C", 0x08006B3C),
              ("SysTick 0x0800DFE4", 0x0800DFE4)):
    print(f"  {nm:26s}: {'可达' if (t in seen) else '不可达'}")

print("\n" + "="*74)
print("【核心】所有物化 TIM3 (0x40000400) 的站点")
print("="*74)
regs = {}
sites = []
for i in insns:
    if i.mnemonic == "movw" and i.op_str.startswith("r"):
        try: lo = int(i.op_str.split("#")[1], 16)
        except (IndexError, ValueError): continue
        if lo == 0x0400: regs[i.op_str.split(",")[0]] = (i.address, lo)
    elif i.mnemonic == "movt" and i.op_str.startswith("r"):
        r = i.op_str.split(",")[0]
        if r in regs:
            try: hi = int(i.op_str.split("#")[1], 16)
            except (IndexError, ValueError): continue
            if hi == 0x4000:
                sites.append((regs[r][0], i.address, r));
            del regs[r]
print(f"  共 {len(sites)} 处\n")
for a, b, r in sites:
    fn = owner(a)
    mark = "★可达" if fn in seen else "  不可达"
    print(f"  {mark}  0x{a:08X}  函数 0x{fn:08X}   reg {r}")
    k = idx[a]
    for j in range(k, min(k+8, len(insns))):
        i2 = insns[j]
        if j > k and i2.address in starts:
            print(f"            ... (函数结束)")
            break
        print(f"          {i2.address:08X}: {i2.mnemonic:8s} {i2.op_str}")
