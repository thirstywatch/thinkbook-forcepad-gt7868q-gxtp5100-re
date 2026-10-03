# -*- coding: utf-8 -*-
"""
round29_master_check.py —— 判定「TF100A 侧代码是否发起 I2C 主机传输」
背景（追加二十六 §18.6 未闭合的决定性判据）：
  「若 TF100A 从不发起 I2C 主机传输 ⇒ 它不可能命令 CA4F ⇒ 主机只能是 GT7868Q。」
本轮已把 0x40005400/0x40005410 的引用点全部反汇编过（round26/27），
现做机械化判定：
  A) 统计该段内所有「启动传输」类操作（在控制寄存器里置 START/GO 位）
  B) 统计是否出现「从地址写入」（把 7bit 从地址装进数据/地址寄存器）
  C) 与已知「从机模式」特征对照（OAR1 从地址、SR1 的 ADDR/RxNE/TxE 位）
输出: cfg_parsed/round29_master_check.txt
"""
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_REG, ARM_OP_IMM, ARM_OP_MEM

FW = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\TB14P_GT7868Q_14030522_20240202.BIN"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfg_parsed", "round29_master_check.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
L = []
def w(s=""):
    L.append(str(s)); print(s, flush=True)

D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)
md.detail = True

LO, HI = 0x1D300, 0x1DB00
insns = list(md.disasm(D[LO:HI], BASE + LO))
w("=" * 78)
w("round29 —— TF100A 侧是否发起 I2C 主机传输（机械化判定）")
w("=" * 78)
w("段 0x%05X-0x%05X  %d 条指令  udf %d" % (LO, HI, len(insns), sum(1 for i in insns if i.mnemonic == "udf")))
w("")

# --- A) 该段内所有 str/strb 到 [reg,#0..0x28] 的写（可能的控制寄存器写） ---
w("-" * 78)
w("### A. 该段内所有对 [reg,#off] (off<=0x28) 的写指令（按寄存器偏移分组）")
w("-" * 78)
by_off = {}
for ins in insns:
    if ins.mnemonic.startswith(("str", "strb", "strh")):
        if not ins.operands:
            continue
        last = ins.operands[-1]
        if last.type == ARM_OP_MEM and last.mem.disp <= 0x28:
            by_off.setdefault(last.mem.disp, []).append((ins.address - BASE, ins.mnemonic, ins.op_str))
for off in sorted(by_off):
    lst = by_off[off]
    w("  [base,#0x%02X]  写 %d 次" % (off, len(lst)))
    for fo, mn, ops in lst[:10]:
        w("       0x%05X  %s %s" % (fo, mn, ops))
    if len(lst) > 10:
        w("       ... 共 %d" % len(lst))
w("")

# --- B) 该段内是否出现「从地址」类立即数（7-bit 从地址 <<1 的形式） ---
w("-" * 78)
w("### B. 该段内全部立即数中，落在「I2C 从地址」合理区间的（0x08-0xF8 偶数）")
w("-" * 78)
imms = {}
for ins in insns:
    for opd in ins.operands:
        if opd.type == ARM_OP_IMM:
            v = opd.imm
            if 0x08 <= v <= 0xF8 and v % 2 == 0:
                imms.setdefault(v, []).append(ins.address - BASE)
w("  候选从地址（值 : 次数 : 位置）:")
for v in sorted(imms):
    sites = imms[v]
    w("     0x%02X : %d  @ %s" % (v, len(sites), ", ".join("0x%X" % s for s in sites[:6])))
w("")
w("  ★ 重点：0x58 (7bit 0x2C) / 0x5A (7bit 0x2D) / 0xB4 / 0xC8 是否出现")
for c in (0x58, 0x5A, 0x5B, 0xB4, 0xB5, 0xC8, 0xE0, 0x78):
    w("     0x%02X : %s" % (c, ("出现 %d 次 @ %s" % (len(imms[c]), imms[c][:4])) if c in imms else "**0 次**"))
w("")

# --- C) 该段内是否出现「置 START / 启动」类位操作 ---
w("-" * 78)
w("### C. 该段内所有 OR 类立即数（可能的「置位启动」操作）")
w("-" * 78)
for ins in insns:
    if ins.mnemonic in ("orr", "orrs", "orr.w") and len(ins.operands) == 2:
        if ins.operands[1].type == ARM_OP_IMM:
            w("  0x%05X  %s %s   (置位 0x%X = bit%d)" %
              (ins.address - BASE, ins.mnemonic, ins.op_str, ins.operands[1].imm, ins.operands[1].imm.bit_length() - 1))
w("")

# --- D) 该段内的间接调用（blx reg）—— 主机发送入口可能在回调里 ---
w("-" * 78)
w("### D. 间接调用 blx/bl reg（可能的主机发送入口）")
w("-" * 78)
for ins in insns:
    if ins.mnemonic in ("blx", "bl") :
        if ins.operands and ins.operands[0].type == ARM_OP_REG:
            w("  0x%05X  %s %s   ★ 间接调用" % (ins.address - BASE, ins.mnemonic, ins.op_str))
w("")
w("=" * 78)
w("round29 结束")
w("=" * 78)
open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("\n[saved] " + OUT)
