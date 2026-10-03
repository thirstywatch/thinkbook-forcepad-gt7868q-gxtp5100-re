# col04_boundary.py — Col04 命令空间边界静态推演（只读分析，不碰任何设备）
#
# 回答四个问题：
#   A. 分发器 0x080091C0 的完整 (类, 值) -> handler 映射（含 movw+cmp 形式，不漏项）
#   B. 分发器的调用者是谁？—— 它到底吃不吃"主机报文"？（决定 Col04 探测有无意义）
#   C. 内部结构 p 的类字节 p[0x104] 是谁写进去的？—— 定位 wire 字节 -> p 偏移 的映射
#   D. 报文长度有没有边界检查？（payload 上限）
import re, struct, bisect, io
import capstone

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
img = open(BIN, 'rb').read()[OFF:OFF + LEN]
END = BASE + LEN

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.skipdata = True
md.detail = False
allins = list(md.disasm(img, BASE))
addr = [i.address for i in allins]
byaddr = {i.address: n for n, i in enumerate(allins)}

out = io.open(r"<LAB>\touchpad-lab\re\col04_boundary_out.txt", "w", encoding="utf-8")
def P(*a):
    s = " ".join(str(x) for x in a)
    out.write(s + "\n")

def k_of(a):
    return bisect.bisect_left(addr, a)

def dump(a, n, tag=""):
    P("\n--- %s @ 0x%08X (%d 条) ---" % (tag, a, n))
    k = k_of(a)
    for i in allins[k:k + n]:
        P("  %08X: %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

P("image 0x%08X..0x%08X  len=%d  指令 %d" % (BASE, END, LEN, len(allins)))

# =====================================================================
# A. 分发器完整提取
#   类 = cmp r0, #0x80 / #0xa0 / #0xa1
#   值 = cmp r0, #imm(>=0x100)   或   movw r?, #imm ; cmp r0, r?
#   目标 = 紧随其后的 beq / bne
# =====================================================================
P("\n" + "=" * 78)
P("A. 分发器 0x080091C0 的完整 (类, 值) -> 目标 映射")
P("=" * 78)
DISP_LO, DISP_HI = 0x080091C0, 0x08009760
disp = [i for i in allins if DISP_LO <= i.address < DISP_HI]

cls = None
rows = []          # (cls, value, branch_addr, branch_mnem, target)
pending_movw = {}  # reg -> imm (等待 cmp)
for n, i in enumerate(disp):
    op = i.op_str
    # 类判定
    m = re.match(r"^r0, #0x([0-9a-f]+)$", op)
    if i.mnemonic.startswith("cmp") and m:
        v = int(m.group(1), 16)
        if v in (0x80, 0xa0, 0xa1):
            cls = v
            continue
        # cmp r0, #imm 形式（值）
        if v >= 0x100:
            for j in disp[n + 1:n + 4]:
                if j.mnemonic.startswith("beq") or j.mnemonic.startswith("bne"):
                    t = j.op_str
                    if t.startswith("#"):
                        rows.append((cls, v, i.address, j.mnemonic, int(t[1:], 16)))
                    elif t.startswith("0x"):
                        rows.append((cls, v, i.address, j.mnemonic, int(t, 16)))
                    break
    if i.mnemonic == "movw" and op.startswith("r"):
        mm = re.match(r"^(r\d+), #0x([0-9a-f]+)$", op)
        if mm:
            pending_movw[mm.group(1)] = int(mm.group(2), 16)
    if i.mnemonic.startswith("cmp") and re.match(r"^r0, r\d+$", op):
        src = op.split(",")[1].strip()
        v = pending_movw.get(src)
        if v is not None and v >= 0x100:
            for j in disp[n + 1:n + 4]:
                if j.mnemonic.startswith("beq") or j.mnemonic.startswith("bne"):
                    t = j.op_str
                    tv = int(t[1:], 16) if t.startswith("#") else (int(t, 16) if t.startswith("0x") else None)
                    if tv is not None:
                        rows.append((cls, v, i.address, j.mnemonic, tv))
                    break

by_cls = {}
for c, v, a, mn, t in rows:
    by_cls.setdefault(c, []).append((v, a, mn, t))

for c in sorted(by_cls, key=lambda x: (x is None, x)):
    rs = by_cls[c]
    P("\n  类 0x%02X   共 %d 个判定点" % (c if c else 0, len(rs)))
    P("    %-10s %-10s %-6s %s" % ("值(hex)", "判定处", "分支", "目标"))
    for v, a, mn, t in sorted(rs, key=lambda x: x[0]):
        # 值的高/低字节拆分，便于判定"子命令落在哪个字节"
        P("    0x%04X     %08X   %-6s -> 0x%08X      [hi=0x%02X lo=0x%02X]" % (v & 0xFFFF, a, mn, t, (v >> 8) & 0xFF, v & 0xFF))

# 默认分支（每个类的兜底）
P("\n  [默认分支] 链条末端没有 beq 命中的 fall-through:")
for c in sorted(by_cls, key=lambda x: (x is None, x)):
    rs = by_cls[c]
    last_a = max(r[1] for r in rs)
    dump(last_a, 8, "类0x%02X 链尾" % c)

# =====================================================================
# B. 调用者：谁调用 0x080091C0？
# =====================================================================
P("\n" + "=" * 78)
P("B. 谁调用分发器 0x080091C0")
P("=" * 78)
TARGET = 0x080091C0
bls = [i.address for i in allins if i.mnemonic.startswith("bl") and i.op_str.startswith("#")
       and int(i.op_str[1:], 16) == TARGET]
lits = [BASE + m.start() for m in re.finditer(re.escape(struct.pack("<I", TARGET)), img)]
mws = []
for n, i in enumerate(allins):
    if i.mnemonic == "movw" and i.op_str == "r1, #0x%x" % (TARGET & 0xFFFF):
        for j in allins[n + 1:n + 3]:
            if j.mnemonic == "movt" and j.op_str.endswith("#0x%x" % (TARGET >> 16)):
                mws.append(i.address)
P("  bl 直接调用: %d 处  %s" % (len(bls), " ".join("%08X" % x for x in bls)))
P("  字面量引用 : %d 处  %s" % (len(lits), " ".join("%08X" % x for x in lits)))
P("  movw/movt  : %d 处  %s" % (len(mws), " ".join("%08X" % x for x in mws)))
for c in bls + mws:
    dump(c - 40, 44, "调用分发器的位置 0x%08X 上下文" % c)

# =====================================================================
# C. p[0x104] 是谁写的？（类字节的来源） + 门铃 bit2(0x20004128)
# =====================================================================
P("\n" + "=" * 78)
P("C. 谁读写 p[0x104] / 门铃 0x20004128 bit2")
P("=" * 78)
P("\n  -- 指令中含 #0x104 / #0x105 / #0x103 的（类字节相关偏移）--")
for i in allins:
    if re.search(r", #0x10[345]$", i.op_str) or re.search(r"#0x10[345]\]", i.op_str):
        P("    %08X  %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

P("\n  -- 所有引用 0x20004128 的位置及其后 5 条 --")
hit = []
for n, i in enumerate(allins):
    if i.mnemonic == "movw" and i.op_str.startswith("r") and i.op_str.endswith("#0x4128"):
        # 确认下一条 movt #0x2000
        if n + 1 < len(allins) and allins[n + 1].mnemonic == "movt" and allins[n + 1].op_str.endswith("#0x2000"):
            hit.append(i.address)
for a in hit:
    k = k_of(a)
    P("    @0x%08X :" % a)
    for i in allins[k:k + 8]:
        P("        %08X  %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

# =====================================================================
# D. 报文长度边界：搜索与长度有关的立即数比较（0x3F/0x40/0x41/0x100 等）
# =====================================================================
P("\n" + "=" * 78)
P("D. 长度/边界检查候选（帧长度字节 p[4] 的用法）")
P("=" * 78)
P("\n  -- 直接读 [rX,#4] 且随后有 cmp #imm 的片段（可能的长度校验）--")
cands = 0
for n, i in enumerate(allins):
    if i.mnemonic == "ldrb" and re.search(r"\[r\d+, #4\]$", i.op_str):
        window = allins[n:n + 6]
        for j in window[1:]:
            if j.mnemonic.startswith("cmp") and "#" in j.op_str:
                P("    %08X  ldrb%s   之后 %08X  %s" % (i.address, i.op_str, j.address, j.mnemonic + " " + j.op_str))
                cands += 1
                break
P("    共 %d 处候选" % cands)

# =====================================================================
# E. 类 0x20（已知安全的"读内存"命令）走的是哪条路？
# =====================================================================
P("\n" + "=" * 78)
P("E. 类 0x20 的处理路径（已知安全命令，用来反证分发器是否吃主机报文）")
P("=" * 78)
P("\n  -- 镜像内所有 cmp r0,#0x20 之后 3 条 --")
cnt = 0
for n, i in enumerate(allins):
    if i.mnemonic.startswith("cmp") and i.op_str in ("r0, #0x20", "r0, #0x20 "):
        P("    @%08X" % i.address)
        for j in allins[n:n + 4]:
            P("        %08X  %-12s %s" % (j.address, j.bytes.hex(), j.mnemonic + " " + j.op_str))
        cnt += 1
        if cnt > 25:
            break
P("    (截断显示，命中 %d 处以上)" % cnt)

out.close()
print("done -> re/col04_boundary_out.txt")
