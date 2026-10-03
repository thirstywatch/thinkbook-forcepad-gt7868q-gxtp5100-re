# vib_reach3.py — 从各 handler 的动作函数出发做 3 层调用图扩展：谁能到马达(TIM3/触觉ctx/波形缓冲/播放)?
import re, struct, io
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
img = open(BIN, "rb").read()[0x19ABC:]
BASE = 0x08000000
END = BASE + len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
allins = list(md.disasm(img, BASE))
idx = {i.address: n for n, i in enumerate(allins)}
out = io.open(r"<LAB>\touchpad-lab\re\vib_reach3_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

def body(entry, maxn=400):
    """从入口顺序反汇编到 pop{...,pc} 或 bx lr（不跨函数）"""
    n = idx.get(entry)
    if n is None:
        return []
    res = []
    for i in allins[n:n + maxn]:
        if i.address != entry:
            if i.mnemonic == "push" or (i.mnemonic.startswith("pop") and "pc" in i.op_str):
                break
        res.append(i)
        if i.mnemonic in ("bx",) and i.op_str == "lr":
            break
    return res

def scan(entry):
    """返回 (bl 目标集合, 引用的绝对地址集合)"""
    calls, refs, regs = set(), set(), {}
    for i in body(entry):
        m = re.match(r"^(\w+), #0x([0-9a-f]+)$", i.op_str)
        if m and i.mnemonic in ("movw", "movt"):
            reg, v = m.group(1), int(m.group(2), 16)
            if i.mnemonic == "movw":
                regs[reg] = v
            else:
                refs.add((v << 16) | regs.get(reg, 0))
        if i.mnemonic.startswith("bl") and i.op_str.startswith("#"):
            calls.add(int(i.op_str[1:], 16))
    return calls, refs

MOTOR_RAM = {0x200040D0: "触觉ctx", 0x200040E8: "波形缓冲", 0x20004094: "状态字", 0x2000495E: "5.7KB缓冲", 0x2000426C: "44B结构"}
def reach(root, depth=3):
    seen, frontier, hits = {root}, [root], []
    for d in range(depth):
        nxt = []
        for f in frontier:
            c, r = scan(f)
            for t in c:
                if BASE <= t < END and t not in seen:
                    seen.add(t); nxt.append(t)
            for v in r:
                if v == 0x40000400: hits.append(("TIM3", f, d))
                if v == 0x40010000: hits.append(("TIM2", f, d))
                if v in MOTOR_RAM: hits.append((MOTOR_RAM[v], f, d))
                if v == 0x08008628: hits.append(("★PLAY", f, d))
                if 0x08008600 <= v < 0x08008900: hits.append(("触觉码0x%X" % v, f, d))
            for t in c:
                if 0x08008600 <= t < 0x08008900: hits.append(("调触觉码0x%X" % t, f, d))
                if t == 0x08008628: hits.append(("★调PLAY", f, d))
        frontier = nxt
    return hits, seen

ROOTS = {
    0x08001694: "A0-05", 0x080013AC: "A0-05/0x0B", 0x08006E28: "A0-0E/0x11/0x1F",
    0x08004CD4: "A0-12/0x24", 0x080049EC: "A0-20", 0x08004A20: "A0-35",
    0x08001F8C: "A0-01/0x32", 0x08001F68: "A0-33", 0x08001FC0: "A0-35b",
    0x08001F70: "A0-35c", 0x08002F30: "A0-14", 0x080088C0: "A0-0B 写波形缓冲",
    0x080086B4: "A0-0D 清/arm", 0x08008868: "A1-0B 读回", 0x0800865C: "A1 读27B@0x1800",
    0x08008628: "播放", 0x08009750: "TIM3 配置",
}
for f, nm in sorted(ROOTS.items(), key=lambda x: x[1]):
    hits, seen = reach(f, 3)
    tag = "  ".join("%s(经0x%X,d=%d)" % h for h in hits[:6]) or "—"
    P("%-18s 0x%08X  可达函数 %3d 个 | 触觉标记: %s" % (nm, f, len(seen), tag))
out.close()
print("done")
