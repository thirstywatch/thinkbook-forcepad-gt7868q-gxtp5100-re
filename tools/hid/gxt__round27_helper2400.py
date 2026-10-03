# -*- coding: utf-8 -*-
"""
round27_helper2400.py —— 解剖 helper 0x2473C 与 0x24700
这是 0x1D40A 等 5 处调用的同一个目标：bl #0x802473c
参数: r0 = 0x40005400 (I2C1 base), r1 = 0x050x010x (5 个不同常量)
若能看清 0x2473C 到底访问 I2C 还是 GPIO，就能定性「这 5 个参数是什么」。
输出: cfg_parsed/round27_helper2400.txt
"""
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round27_helper2400.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
L = []
def w(s=""):
    L.append(str(s)); print(s, flush=True)

D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = False

w("=" * 78)
w("round27 —— helper 0x2473C / 0x24700 解剖")
w("=" * 78)
w("")

# helper 0x24700 与 0x2473C（审计说取位 [20:16]=引脚 [31:22]=端口）
for start, name in ((0x24700, "helper@0x24700"), (0x2473C, "helper@0x2473C")):
    insns = list(md.disasm(D[start:start + 0x100], BASE + start))
    w("-" * 78)
    w("### %s" % name)
    w("-" * 78)
    for ins in insns:
        fo = ins.address - BASE
        w("  0x%05X  %s %s" % (fo, ins.mnemonic, ins.op_str))
    w("")

# 顺带把 0x24700 附近整体打印（可能有常量池/寄存映射表）
w("-" * 78)
w("### 0x246E0-0x248A0 全景")
w("-" * 78)
insns = list(md.disasm(D[0x246E0:0x248A0], BASE + 0x246E0))
w("共 %d 条, udf %d" % (len(insns), sum(1 for i in insns if i.mnemonic == "udf")))
for ins in insns:
    w("  0x%05X  %s %s" % (ins.address - BASE, ins.mnemonic, ins.op_str))
w("")
open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("\n[saved] " + OUT)
