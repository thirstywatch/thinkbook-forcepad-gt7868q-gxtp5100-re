# col04_boundary2.py — 追帧缓冲边界：谁写类字节 0x20004238(=p+0x104)？帧缓冲多大？
# 已知锚点：p = 0x20004134（=0x20004128+0xC），响应缓冲 = 0x20004128+0x8C = 0x200041B4
import re, struct, bisect, io
import capstone

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
img = open(BIN, 'rb').read()[OFF:OFF + LEN]
END = BASE + LEN
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
md.skipdata = True
allins = list(md.disasm(img, BASE))
addr = [i.address for i in allins]
out = io.open(r"<LAB>\touchpad-lab\re\col04_boundary2_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")
def k_of(a): return bisect.bisect_left(addr, a)
def dump(a, n, tag=""):
    P("\n--- %s @ 0x%08X (%d 条) ---" % (tag, a, n))
    k = k_of(a)
    for i in allins[k:k + n]:
        mark = ""
        if re.search(r"#0x(4128|4134|4238|41B4|8c|104|110|11c|58)\b", i.op_str) or "#0x" in i.op_str and re.search(r"movw", i.mnemonic):
            mark = "   <<"
        P("  %08X: %-12s %s%s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str, mark))

# 1) 主循环 / 调用分发器的那个函数（往上找 prologue）
P("=" * 78)
P("1) 调用分发器的主循环函数（0x0800AD60..0x0800AE40）")
P("=" * 78)
dump(0x0800AD60, 110, "主循环")

# 2) 帧缓冲的初始化/清零者：0x08008A6E 所在函数（I2C1 区）
P("\n" + "=" * 78)
P("2) 0x08008A6E 所在函数（疑为 I2C 收包/入队）")
P("=" * 78)
dump(0x08008A40, 110, "I2C 收包区")

# 3) 写类字节的地方 0x080097B0
P("\n" + "=" * 78)
P("3) 类字节写入者 0x080097B0 所在函数")
P("=" * 78)
dump(0x08009760, 60, "写 p[0x104]")

# 4) 0x08008FAC 读 p[0x104]/p[0x105] —— 可能是"回应打包"
P("\n" + "=" * 78)
P("4) 0x08008F8C..0x08009020（读 p[0x104]/p[0x105]）")
P("=" * 78)
dump(0x08008F8C, 60, "读 p[0x104]")

# 5) 全镜像搜索：立即数 0x20004134 / 0x20004238 / 0x200041B4 的 movw 引用
P("\n" + "=" * 78)
P("5) 谁引用 0x20004134 / 0x20004238 / 0x200041B4")
P("=" * 78)
for tgt, nm in [(0x20004134, "帧缓冲 p+0"), (0x20004238, "类字节 p+0x104"), (0x200041B4, "响应缓冲 p+0x8C")]:
    P("\n  -- %s = 0x%08X --" % (nm, tgt))
    hits = []
    for n, i in enumerate(allins):
        if i.mnemonic == "movw" and i.op_str.endswith("#0x%x" % (tgt & 0xFFFF)):
            hits.append(i.address)
    # 也找 add.w rX, rY, #imm 形式的相对寻址
    P("     movw 直接命中: %d 处  %s" % (len(hits), " ".join("%08X" % h for h in hits[:20])))
    lit = [BASE + m.start() for m in re.finditer(re.escape(struct.pack("<I", tgt)), img)]
    P("     字面量命中: %d 处  %s" % (len(lit), " ".join("%08X" % h for h in lit[:10])))
    if tgt == 0x20004134:
        P("     （帧缓冲基址是 0x20004128+0xC 算出来的，故 movw 命中少属正常）")

# 6) 帧长边界：搜 movs rX,#0x58 / cmp ...#0x58 / 0x57 / 0x5A 在帧缓冲相关函数
P("\n" + "=" * 78)
P("6) memcpy/memset 长度参数（帧缓冲大小线索）")
P("=" * 78)
for n, i in enumerate(allins):
    if i.mnemonic in ("movs", "mov.w") and re.search(r"#0x(58|57|59|5a|50|40|3f)\b", i.op_str):
        nxt = allins[n + 1] if n + 1 < len(allins) else None
        if nxt and nxt.mnemonic.startswith("bl"):
            P("    %08X  %-20s  -> %08X %s" % (i.address, i.mnemonic + " " + i.op_str, nxt.address, nxt.mnemonic + " " + nxt.op_str))

out.close()
print("done")
