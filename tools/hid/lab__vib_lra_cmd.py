# vib_lra_cmd.py — 关键：dispatcher 的哪些命令会调进 LRA/触觉区（0x080086xx-0x080088xx）？
import re, struct, io
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
img = data[0x19ABC:]
BASE = 0x08000000
END = BASE + len(img)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
allins = list(md.disasm(img, BASE))
out = io.open(r"<LAB>\touchpad-lab\re\vib_lra_cmd_out.txt", "w", encoding="utf-8")
def P(*a): out.write(" ".join(str(x) for x in a) + "\n")

def show(a, b, title):
    P("\n===== %s  [0x%08X..0x%08X] =====" % (title, a, b))
    for i in allins:
        if a <= i.address < b:
            P("  %08X: %-12s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

# 1) class 0xA0 -> 0x0B00 / 0x0D00 的 handler 桩
show(0x08009340, 0x08009390, "handler 桩 (0x0B00 / 0x0D00 等)")
# 2) else 分支 / 第二张表（class 0xA1）
show(0x080093C0, 0x08009420, "else 分支 = 第二张表")
# 3) LRA / 触觉区
show(0x08008600, 0x08008700, "LRA 区 A (0x080086xx：含 0x8628 play / 0x86B4)")
show(0x08008840, 0x08008900, "LRA 区 B (0x080088xx：含 0x8858 / 0x88C0)")

# 4) 谁调用这些地址
P("\n" + "=" * 78)
P("=== 调用者统计 ===")
TARGETS = [0x08008628, 0x080086B4, 0x080088C0, 0x08008858, 0x08008704, 0x08009750, 0x08008FE8, 0x0800903E]
for t in TARGETS:
    callers = []
    for i in allins:
        if i.mnemonic.startswith("bl") and i.op_str.startswith("#"):
            if int(i.op_str[1:], 16) == t:
                callers.append(i.address)
    # 字面量 / movw+movt 引用
    pat = struct.pack("<I", t)
    lit = [BASE + m.start() for m in re.finditer(re.escape(pat), img)]
    P("  0x%08X  bl 调用者 %d 个 %s" % (t, len(callers), " ".join("%X" % c for c in callers[:8])))
    if lit:
        P("            字面量出现 %d 处: %s" % (len(lit), " ".join("%X" % c for c in lit[:8])))

# 5) dispatcher 完整子命令表（class 0xA0 与第二张表）
P("\n" + "=" * 78)
P("=== dispatcher 子命令 -> 目标 汇总 ===")
for i in allins:
    if 0x080091C0 <= i.address < 0x08009410 and i.mnemonic in ("beq", "beq.w") and i.op_str.startswith("#"):
        P("  %08X  %s" % (i.address, i.op_str))

out.close()
print("done")
