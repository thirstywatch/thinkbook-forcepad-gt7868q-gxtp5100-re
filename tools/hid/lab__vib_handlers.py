# vib_handlers.py — 把两张表(类0xA0 / 0xA1)全部子命令的 handler 逐条解出：谁碰触觉区？
import re, struct, io
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
img = open(BIN, "rb").read()[0x19ABC:]
BASE = 0x08000000
END = BASE + len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
allins = list(md.disasm(img, BASE))
byaddr = {i.address: n for n, i in enumerate(allins)}
out = io.open(r"<LAB>\touchpad-lab\re\vib_handlers_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

# ---- 1) 抽取 dispatcher 的 (类, 子命令) -> handler ----
disp = [i for i in allins if 0x080091C0 <= i.address < 0x08009750]
pairs = []
cls = None
for n, i in enumerate(disp):
    if i.mnemonic.startswith("cmp") and i.op_str.startswith("r0, #"):
        val = int(i.op_str.split("#")[1], 16)
        if val == 0x80: cls = 0x80; continue
        if val == 0xa0: cls = 0xA0; continue
        if val == 0xa1: cls = 0xA1; continue
        if val >= 0x100 and val % 0x100 == 0:
            for j in disp[n:n + 4]:
                if j.mnemonic.startswith("beq") and j.op_str.startswith("#"):
                    pairs.append((cls, val >> 8, int(j.op_str[1:], 16)))
                    break

# ---- 2) 每个 handler：反汇编到终止，收集 bl 目标 / 绝对地址 ----
def analyze(entry, maxn=70):
    calls, refs, ramw, per = [], [], [], []
    n = byaddr.get(entry)
    if n is None:
        return None
    regs = {}
    cnt = 0
    for i in allins[n:]:
        if i.address != entry and (i.mnemonic in ("push",) or i.mnemonic.startswith("pop")):
            break
        cnt += 1
        if cnt > maxn:
            break
        m = re.match(r"^(\w+), #0x([0-9a-f]+)$", i.op_str)
        if m and i.mnemonic in ("movw", "movt"):
            reg = m.group(1); v = int(m.group(2), 16)
            if i.mnemonic == "movw":
                regs[reg] = v
            else:
                full = (v << 16) | regs.get(reg, 0)
                refs.append((i.address, full))
        if i.mnemonic.startswith("bl") and i.op_str.startswith("#"):
            calls.append((i.address, int(i.op_str[1:], 16)))
        if i.mnemonic in ("str", "strh", "strb") and i.op_str.startswith("r") and "[r" in i.op_str:
            reg = i.op_str.split("[")[1].split(",")[0].strip("] ")
            base = regs.get(reg)
            if base is not None:
                if 0x20000000 <= base < 0x20008000:
                    ramw.append(base)
                elif base >= 0x40000000:
                    per.append(base)
        if i.mnemonic in ("bx", "pop") and "pc" in i.op_str:
            break
    return calls, refs, ramw, per

P("类   子命令  handler     调用  ->  触觉相关标记")
P("-" * 100)
HAIR = {0x40000400: "TIM3", 0x40010000: "TIM2", 0x40010800: "GPIOA"}
for cls, sub, h in pairs:
    r = analyze(h)
    if r is None:
        P("%-5s 0x%02X    0x%08X  <入口不在镜像>" % ("%02X" % cls, sub, h)); continue
    calls, refs, ramw, per = r
    marks = []
    for _, t in calls:
        if 0x08008600 <= t < 0x08008900: marks.append("★触觉码 0x%08X" % t)
        if t == 0x08008628: marks.append("★PLAY!")
    for _, v in refs:
        if 0x08008600 <= v < 0x08008900: marks.append("★触觉码字面量 0x%08X" % v)
        if v in (0x200040D0, 0x200040E8, 0x20004094, 0x2000495E, 0x2000426C): marks.append("★触觉RAM 0x%08X" % v)
        if v in HAIR: marks.append("★" + HAIR[v])
    for b in ramw:
        if 0x20004000 <= b <= 0x20005000: marks.append("★写触觉RAM 0x%08X" % b)
    for b in per:
        if b in HAIR: marks.append("★写" + HAIR[b])
    P("%-5s 0x%02X    0x%08X  %2d 条  %s" % ("%02X" % cls, sub, h, len(calls),
      "  ".join(sorted(set(marks))) if marks else ""))

P("\n\n=== 触觉相关 handler 的完整调用链 ===")
for cls, sub, h in pairs:
    r = analyze(h)
    if not r:
        continue
    calls, refs, ramw, per = r
    if any(0x08008600 <= t < 0x08008900 or t == 0x08008628 for _, t in calls) or \
       any(v in (0x200040D0, 0x200040E8, 0x20004094) for _, v in refs):
        P("  [类%02X 子命令0x%02X] handler 0x%08X" % (cls, sub, h))
        for a, t in calls:
            P("      %08X bl -> 0x%08X" % (a, t))
        for a, v in refs:
            P("      %08X 引用 0x%08X" % (a, v))

# ---- 3) 谁能"启动"播放：0x08008628 / TIM3 使能 helper 的全部引用 ----
P("\n\n=== 播放入口与 TIM3 使能 helper 的引用者（含字面量/movw+movt） ===")
for tgt in (0x08008628, 0x0800BD44, 0x0800BD30, 0x08008858):
    callers = [i.address for i in allins if i.mnemonic.startswith("bl") and i.op_str == "#0x%x" % tgt]
    lit = [BASE + m.start() for m in re.finditer(re.escape(struct.pack("<I", tgt)), img)]
    mw = []
    for n, i in enumerate(allins):
        if i.mnemonic == "movw" and i.op_str == "r1, #0x%x" % (tgt & 0xFFFF):
            for j in allins[n + 1:n + 3]:
                if j.mnemonic == "movt" and j.op_str.endswith("#0x%x" % (tgt >> 16)):
                    mw.append(i.address)
    P("  0x%08X: bl=%d %s | 字面量=%d %s | movw/movt=%d %s" % (
        tgt, len(callers), " ".join("%X" % c for c in callers[:6]),
        len(lit), " ".join("%X" % c for c in lit[:6]),
        len(mw), " ".join("%X" % c for c in mw[:6])))

out.close()
print("done")
