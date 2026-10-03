# col04_boundary3.py — 追"帧入队"路径：谁写类字节 ctx+0x110？谁拨门铃 0x08008B5C？
import re, struct, bisect, io
import capstone

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
img = open(BIN, 'rb').read()[OFF:OFF + LEN]
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.skipdata = True
allins = list(md.disasm(img, BASE))
addr = [i.address for i in allins]
out = io.open(r"<LAB>\touchpad-lab\re\col04_boundary3_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")
def k_of(a): return bisect.bisect_left(addr, a)
def dump(a, n, tag=""):
    P("\n--- %s @ 0x%08X ---" % (tag, a))
    k = k_of(a)
    for i in allins[k:k + n]:
        P("  %08X: %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
def callers(tgt):
    bls = [i.address for i in allins if i.mnemonic.startswith("bl") and i.op_str.startswith("#")
           and int(i.op_str[1:], 16) == tgt]
    lit = [BASE + m.start() for m in re.finditer(re.escape(struct.pack("<I", tgt)), img)]
    mws = []
    for n, i in enumerate(allins):
        if i.mnemonic == "movw" and i.op_str.endswith("#0x%x" % (tgt & 0xFFFF)):
            for j in allins[n + 1:n + 3]:
                if j.mnemonic == "movt" and j.op_str.endswith("#0x%x" % (tgt >> 16)):
                    mws.append(i.address)
    return bls, lit, mws

# 1) 门铃 & 收包函数 & 上下文初始化器的调用者
P("=" * 78)
P("1) 关键函数的调用者（决定'谁能把帧塞进 0x20004134'）")
P("=" * 78)
for tgt, nm in [
    (0x08008B5C, "★门铃（置 bit2 of 0x20004128）"),
    (0x08008B38, "置 bit1 + 写 GPIOA"),
    (0x08008ADC, "按参数置/清 bit1"),
    (0x08008B78, "收包/入队候选（带参数）"),
    (0x08008A4C, "上下文初始化器（写 0x58、三个回调）"),
    (0x080091C0, "分发器"),
    (0x08008F8C, "读 p[0x104] 的候选"),
    (0x080097B0, "写 p[0x104] 的候选"),
    (0x0800DB39, "回调 A（transport vtable）"),
    (0x0800DB5D, "回调 B"),
    (0x0800DADD, "回调 C"),
    (0x0800D6F5, "★触觉播放回调"),
]:
    bls, lit, mws = callers(tgt)
    P("\n  %-38s 0x%08X" % (nm, tgt))
    P("     bl 调用: %d  %s" % (len(bls), " ".join("%08X" % x for x in bls[:12])))
    P("     字面量 : %d  %s" % (len(lit), " ".join("%08X" % x for x in lit[:12])))
    P("     movw   : %d  %s" % (len(mws), " ".join("%08X" % x for x in mws[:12])))

# 2) 收包函数 0x08008B78 全文
P("\n" + "=" * 78)
P("2) 0x08008B78 起的收包函数全文")
P("=" * 78)
dump(0x08008B78, 120, "收包候选")

# 3) 全镜像：所有对偏移 #0x110 / #0x112 / #0x114 / #0x118 / #0x11a / #0x11c 的访问
P("\n" + "=" * 78)
P("3) 上下文结构 0x20004128 的字段访问（#0x110..#0x12c）")
P("=" * 78)
for i in allins:
    if re.search(r", #0x1(1[0-9a-f]|2[0-9a-c])\]?$", i.op_str) and i.mnemonic in ("ldrb", "str", "strb", "ldr", "strh", "ldrh", "ldrb.w", "strb.w", "str.w", "ldr.w", "strh.w", "ldrh.w"):
        P("  %08X  %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

# 4) 谁调用 0x08001628（类 0x80 的 handler）
P("\n" + "=" * 78)
P("4) 类 0x80 handler 0x08001628 概要")
P("=" * 78)
dump(0x08001628, 40, "类0x80 handler")

# 5) 帧缓冲可读性：谁 memcpy 进 0x20004134
P("\n" + "=" * 78)
P("5) 往 0x20004134 写数据的代码（add.w rX,rY,#0xc 形式 + 紧随的 bl）")
P("=" * 78)
for n, i in enumerate(allins):
    if i.mnemonic == "add.w" and re.search(r"#0xc$", i.op_str):
        win = allins[n:n + 8]
        for j in win[1:]:
            if j.mnemonic.startswith("bl"):
                P("  %08X  %-22s  -> %08X %s" % (i.address, i.mnemonic + " " + i.op_str, j.address, j.mnemonic + " " + j.op_str))
                break

out.close()
print("done")
