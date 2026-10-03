# col04_boundary5.py — 最后一环：分发前的服务函数 0x08003C64 / 链路层状态机 0x08003B00..0x08003C90
import re, struct, bisect, io
import capstone

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
img = open(BIN, 'rb').read()[OFF:OFF + LEN]
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.skipdata = True
allins = list(md.disasm(img, BASE))
addr = [i.address for i in allins]
out = io.open(r"<LAB>\touchpad-lab\re\col04_boundary5_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")
def k_of(a): return bisect.bisect_left(addr, a)
def dump(a, n, tag=""):
    P("\n--- %s @ 0x%08X ---" % (tag, a))
    k = k_of(a)
    for i in allins[k:k + n]:
        P("  %08X: %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

P("=" * 78)
P("1) 链路层状态机 / 分发前的服务函数 0x08003B00..0x08003CC0")
P("=" * 78)
dump(0x08003B00, 230, "链路层")

# 找所有把 r4 设为 0x20004128 的位置（那一族函数）
P("\n" + "=" * 78)
P("2) 该族函数的共同基址确认：谁把寄存器设为 0x20004128")
P("=" * 78)
for n, i in enumerate(allins):
    if i.mnemonic == "movw" and re.search(r"#0x4128$", i.op_str) and 0x08003A00 <= i.address <= 0x08003D00:
        P("  %08X  %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

P("\n" + "=" * 78)
P("3) 0x08003C64 的调用者")
P("=" * 78)
bls = [i.address for i in allins if i.mnemonic.startswith("bl") and i.op_str.startswith("#")
       and int(i.op_str[1:], 16) == 0x08003C64]
P("  0x08003C64 调用者: %s" % " ".join("%08X" % x for x in bls))

P("\n" + "=" * 78)
P("4) 全镜像：与 0x58(=88) 或帧长相关比较（在 0x08003A00..0x08003D00 与 0x08008800..0x08008C00 内）")
P("=" * 78)
for i in allins:
    if (0x08003A00 <= i.address <= 0x08003D00 or 0x08008800 <= i.address <= 0x08008C00):
        if i.mnemonic.startswith("cmp") and re.search(r"#0x(58|56|5a|59|57)\b", i.op_str):
            P("  %08X  %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

out.close()
print("done")
