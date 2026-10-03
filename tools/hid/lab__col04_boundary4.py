# col04_boundary4.py — 追"主机报文 -> 内部帧缓冲"的解析器：
#   写类字节 ctx+0x110 的函数（0x08005376 所在）
#   I2C1 从机 ISR 区（0x08008900..0x08008A4C）——主机下行报文的入口
import re, struct, bisect, io
import capstone

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
img = open(BIN, 'rb').read()[OFF:OFF + LEN]
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.skipdata = True
allins = list(md.disasm(img, BASE))
addr = [i.address for i in allins]
out = io.open(r"<LAB>\touchpad-lab\re\col04_boundary4_out.txt", "w", encoding="utf-8")
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
    return bls

P("=" * 78)
P("1) 写类字节 ctx+0x110 的函数区（0x080052A8..0x08005420）")
P("=" * 78)
dump(0x080052A8, 130, "类字节写入者")

P("\n" + "=" * 78)
P("2) 该函数的入口与调用者")
P("=" * 78)
# 往上找 push {...,lr} 作为函数入口
k0 = k_of(0x08005376)
entry = None
for j in range(k0, max(0, k0 - 200), -1):
    if allins[j].mnemonic == "push" and "lr" in allins[j].op_str:
        entry = allins[j].address
        break
P("  推测函数入口: 0x%08X" % entry if entry else "  未找到入口")
if entry:
    P("  调用者: %s" % " ".join("%08X" % x for x in callers(entry)))

P("\n" + "=" * 78)
P("3) I2C1 从机 ISR 区（0x080088C0..0x08008A4C）—— 主机下行入口")
P("=" * 78)
dump(0x080088C0, 200, "I2C1 ISR 区")
P("\n  -- 0x08008936 长度检查前后 --")
dump(0x08008920, 24, "长度检查")

out.close()
print("done")
