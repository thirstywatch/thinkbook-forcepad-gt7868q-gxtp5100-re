"""独立复算：用 capstone 直接线性反汇编整个明文段（遇不可解码则跳过），
统计每条 bl/blx/b.w 的目标，并与"基于 asm.txt 文本解析"的结果交叉比对。

用途：验证 i2c_master_probe2.py 的 HAL 调用点清单不是文本解析的产物。
"""
import os, collections
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "touchpad_GT7868Q_fw.bin")
REGION_OFF, REGION_ADDR, LEN = 0x19ABC, 0x08005000, 56480

data = open(BIN, "rb").read()
code = data[REGION_OFF:REGION_OFF + LEN]

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.detail = True

calls = collections.defaultdict(list)
addr = REGION_ADDR
end = REGION_ADDR + LEN
bad = 0
total = 0
while addr < end:
    got = list(md.disasm(code[addr - REGION_ADDR: addr - REGION_ADDR + 4], addr, count=1))
    if not got:
        bad += 1
        addr += 2
        continue
    ins = got[0]
    total += 1
    if ins.mnemonic in ("bl", "blx", "b") and ins.operands and ins.operands[0].type == 2:  # ARM_OP_IMM
        calls[ins.operands[0].imm].append(ins.address)
    addr += ins.size

print("capstone 解码 %d 条指令，跳过 %d 个不可解码位置" % (total, bad))

HAL = {0x0800FBF8: "wr_DR(+0x10)", 0x0800FC0C: "CR1 PE", 0x0800FC20: "CR2 IT",
       0x0800FC44: "ClearFlag", 0x0800FC80: "GetFlagStatus", 0x0800F9CC: "CR1 ACK",
       0x0800F9F8: "CR1 POS", 0x0800FD24: "OAR1", 0x0800FA20: "I2C_Init",
       0x0800F81C: "gpio_cfg", 0x0800F80C: "gpio_BSRR", 0x0800FE3C: "nvic_prio",
       0x0800F7FC: "gpio_?,", 0x080101D8: "clk"}
print("\n=== capstone 复算的 I2C HAL 调用点 ===")
for t in sorted(HAL):
    if t in calls:
        print("  0x%08X %-14s x%d : %s" % (t, HAL[t], len(calls[t]), " ".join("%08X" % s for s in calls[t])))
    else:
        print("  0x%08X %-14s x0  (未被调用)" % (t, HAL[t]))

# 直接引用 I2C1 基址的 movw/movt 对（capstone 版）
print("\n=== capstone 复算：movw #0x54NN 站点 ===")
addr = REGION_ADDR
seen = []
prev = {}
while addr < end:
    got = list(md.disasm(code[addr - REGION_ADDR: addr - REGION_ADDR + 4], addr, count=1))
    if not got:
        addr += 2
        continue
    ins = got[0]
    if ins.mnemonic == "movw" and len(ins.operands) == 2 and ins.operands[1].type == 2:
        imm = ins.operands[1].imm
        if (imm & 0xFF00) == 0x5400:
            seen.append((ins.address, ins.op_str))
    addr += ins.size
for a, o in seen:
    print("  %08X  %s" % (a, o))
print("  共 %d 个" % len(seen))
