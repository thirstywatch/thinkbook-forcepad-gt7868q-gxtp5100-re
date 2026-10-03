# -*- coding: utf-8 -*-
"""第二层：0x20004128 是什么？谁设 bit2（门铃）？分发器是一次性还是循环？
"""
import re, bisect, capstone, struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
data = open(BIN, 'rb').read()[OFF:OFF + LEN]

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.skipdata = True
insns = list(md.disasm(data, BASE))
addr = [i.address for i in insns]


def dis(a, n=48, tag=""):
    k = bisect.bisect_left(addr, a)
    print(f"\n===== {tag} @ {a:#010x} ({n} 条) =====")
    for i in insns[k:k + n]:
        print(f"{i.address:#010x}: {i.mnemonic:9s} {i.op_str}")


print("### A. 全部 movw #0x4128 站点（0x20004128 = 全局状态结构）")
for k, i in enumerate(insns):
    if i.mnemonic == 'movw' and '#0x4128' in i.op_str:
        print(f"  {i.address:#010x}  (第 {k} 条)")

print("\n\n### B. 序列器尾部：0x0800AD64 到底多长、是否循环")
dis(0x0800AE24, 60, "序列器尾")

print("\n\n### C. 谁引用 0x0800AD64（bl / 分支 / 函数指针）")
pat = {0x0800ad64, 0x0800ad65}
for i in insns:
    if i.mnemonic in ('bl', 'blx', 'b', 'b.w') and ('0x800ad64' in i.op_str.lower() or '0x800ad65' in i.op_str.lower()):
        print(f"  {i.address:#010x}: {i.mnemonic} {i.op_str}")
for k in range(0, LEN - 4):
    if struct.unpack_from('<I', data, k)[0] in pat:
        print(f"  字面量 @ {BASE+k:#010x} = {struct.unpack_from('<I', data, k)[0]:#010x}")

print("\n\n### D. bit2 门铃：0x08008B00 – 0x08008B90 全貌")
dis(0x08008B00, 60, "门铃区")

print("\n\n### E. 分发器早退目标 0x0800974A 附近")
dis(0x08009728, 26, "早退目标")

print("\n\n### F. 0x08003A1C（I2C1 侧操作 0x20004134 的函数）")
dis(0x08003A1C, 30, "0x08003A1C")

print("\n\n### G. 谁 bl 到 0x08008B78 / 0x08008B5C 区")
for tgt in (0x8008b78, 0x8008b3a, 0x8008b5c, 0x8008b04, 0x8008af0):
    hits = [f"{i.address:#010x}" for i in insns
            if i.mnemonic in ('bl', 'blx') and f"{tgt:#x}" in i.op_str.lower().replace('0x800', '0x800')]
    print(f"  bl→{tgt:#010x}: {hits if hits else '无'}")
