# vib_tables.py —— 找函数指针表（固件真正的分发机制），并做调用图自检
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct, bisect
from collections import defaultdict

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read(); IMG = 0x19ABC; BASE = 0x08000000
img = data[IMG:]; END = BASE + len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN); md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
idx = {i.address: k for k, i in enumerate(insns)}

starts = set()
for k in range(0, 0x100, 4):
    v = struct.unpack_from("<I", img, k)[0]
    if BASE <= v < END: starts.add(v & ~1)
bl_raw = []
for i in insns:
    if i.mnemonic in ("bl", "bl.w"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if BASE <= v < END: bl_raw.append((i.address, v)); starts.add(v)
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

def bfs(src, dst, maxn=100000):
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

print("="*74)
print("【自检】已知必然被调用的函数，从各入口是否可达？")
print("="*74)
SANITY = {
    "0x08009750 LRA配置(必然被调)": 0x08009750,
    "0x08008704 PWM配置(必然被调)": 0x08008704,
    "0x0800D6F4 波形回调": 0x0800D6F4,
    "0x08008FE8 TIM2初始化": 0x08008FE8,
    "0x0800AA20 主循环": 0x0800AA20,
}
for nm, t in SANITY.items():
    paths = []
    for enm, ea in (("复位", 0x08000154), ("主循环", 0x0800AA20), ("分发器", 0x080091C0), ("DMA1", 0x08006B3C)):
        p = bfs(owner(ea) or ea, t)
        paths.append(f"{enm}{'✓' if p else '✗'}")
    print(f"  {nm:34s} 从 复位/主循环/分发器/DMA1 可达: {' '.join(paths)}")

print("\n" + "="*74)
print("【关键】整个容器 BIN（含配置记录区）中，哪些地方出现 LRA 相关指针？")
print("="*74)
for nm, fn in (("播放包装", 0x08008628), ("波形回调", 0x0800D6F4),
               ("LRA配置", 0x08009750), ("PWM配置", 0x08008704),
               ("间接调用器", 0x08008858), ("LRA上下文0x200040D0", 0x200040D0)):
    hits = []
    for val in (fn, fn | 1):
        pat = struct.pack("<I", val); s0 = 0
        while True:
            j = data.find(pat, s0)
            if j < 0: break
            hits.append((j, "|1" if val & 1 else "  ")); s0 = j + 1
    locs = [f"0x{o:06X}{t}" + ("(明文=镜像内)" if o >= IMG else "(记录区)") for o, t in hits]
    print(f"  {nm:22s} 0x{fn:08X}: {locs if locs else '【全容器无引用】'}")

print("\n" + "="*74)
print("【函数指针表】明文镜像里连续 >=4 个 Thumb 指针的区段")
print("="*74)
def is_thumb(w):
    return (w & 1) == 1 and BASE <= (w & ~1) < END
runs = []
i = 0
n = len(img) // 4
words = list(struct.unpack_from("<%dI" % n, img, 0))
while i < n:
    if is_thumb(words[i]):
        j = i
        while j < n and is_thumb(words[j]): j += 1
        if j - i >= 4:
            runs.append((i, j))
        i = j
    else:
        i += 1
print(f"  找到 {len(runs)} 个表")
for a, b in runs:
    va, vb = BASE + a*4, BASE + b*4
    entries = [words[t] & ~1 for t in range(a, min(b, a+20))]
    tag = ""
    if any(e in (0x08008628, 0x0800D6F4, 0x08009750, 0x08008704) for e in entries):
        tag = "   ★★★ 含震动相关函数 ★★★"
    print(f"  0x{va:08X}-0x{vb:08X}  ({b-a} 项){tag}")
    print(f"      {[hex(e) for e in entries]}")
