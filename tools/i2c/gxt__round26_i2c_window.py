# -*- coding: utf-8 -*-
"""
round26_i2c_window.py —— 不做数据流，直接打印每个 I2C1 引用点前后 40 条指令的反汇编
让「是不是 I2C 主机驱动、从地址是多少」从原始汇编里直接读出来。
输出: cfg_parsed/round26_i2c_window.txt
"""
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round26_i2c_window.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
L = []
def w(s=""):
    L.append(str(s)); print(s, flush=True)

D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = False

SITES = [0x1D40A, 0x1D436, 0x1D45E, 0x1D486, 0x1D4AE, 0x1D4F0, 0x1D51C,
         0x1D554, 0x1D57C, 0x1D5A8, 0x1D614, 0x1D644, 0x241AC]

w("=" * 78)
w("round26 —— I2C1 引用点原始反汇编窗口（人工可读）")
w("=" * 78)
w("")

# 这些站点高度聚集在 0x1D40A-0x1D644，实际是同一段代码的多处引用。
# 直接反汇编整段，标注引用点。
LO, HI = 0x1D380, 0x1D6A0
insns = list(md.disasm(D[LO:HI], BASE + LO))
w("段 0x%05X-0x%05X, %d 条指令, udf %d" % (LO, HI, len(insns), sum(1 for i in insns if i.mnemonic == "udf")))
w("")
siteset = set(SITES)
for ins in insns:
    fo = ins.address - BASE
    mark = ""
    if fo in siteset:
        mark = "   <<<=== I2C1 引用点"
    elif any(abs(fo - s) <= 4 for s in siteset):
        mark = "   <<< 邻近"
    w("  0x%05X  %-34s%s" % (fo, "%s %s" % (ins.mnemonic, ins.op_str), mark))
w("")
w("=" * 78)
w("round26 结束")
w("=" * 78)
open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("\n[saved] " + OUT)
