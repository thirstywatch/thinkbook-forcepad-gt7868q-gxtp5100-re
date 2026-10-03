# -*- coding: utf-8 -*-
"""最后一轮：① 确认主循环 ② 谁能拨响门铃 bit2 ③ 门铃函数在整容器里的引用
"""
import re, bisect, struct, capstone

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
full = open(BIN, 'rb').read()
data = full[OFF:OFF + LEN]

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.skipdata = True
insns = list(md.disasm(data, BASE))
addr = [i.address for i in insns]


def dis(a, n=40, tag=""):
    k = bisect.bisect_left(addr, a)
    print(f"\n-- {tag} @ {a:#010x} --")
    for i in insns[k:k + n]:
        print(f"   {i.address:#010x}: {i.mnemonic:9s} {i.op_str}")


dis(0x0800ADF4, 36, "主循环体（确认回边）")

print("\n\n### 谁 bl 到循环顶函数 0x08003C64")
for i in insns:
    if i.mnemonic in ('bl', 'blx') and '0x8003c64' in i.op_str.lower():
        print(f"   {i.address:#010x}: {i.mnemonic} {i.op_str}")

print("\n\n### 整容器（含加密区）搜门铃三函数的引用字面量")
for tgt in (0x08008AF1, 0x08008AF0, 0x08008B39, 0x08008B38, 0x08008B5D, 0x08008B5C):
    hits = [f"{k:#x}" for k in range(0, len(full) - 4)
            if struct.unpack_from('<I', full, k)[0] == tgt]
    print(f"   字面量 {tgt:#010x}: {hits if hits else '无'}")

print("\n\n### 数据流：以 0x20004128 为基址的写指令（写的是 g[0] / g[+0x8c] 等）")
# 收集 movw rX,#0x4128 的寄存器，随后 60 条内对该寄存器的 strb/str 写
for k, i in enumerate(insns):
    if i.mnemonic == 'movw' and '#0x4128' in i.op_str:
        regs = set([i.op_str.split(',')[0].strip()])
        for j in insns[k + 1:k + 60]:
            if j.mnemonic in ('mov',) and j.op_str.split(',')[1].strip() in regs:
                regs.add(j.op_str.split(',')[0].strip())
            if j.mnemonic.startswith('str') and re.search(r'\[(' + '|'.join(regs) + r')(,\s*#0)?\]', j.op_str):
                print(f"   {j.address:#010x}: {j.mnemonic:8s} {j.op_str}   (基址出自 {i.address:#010x})")

print("\n\n### 谁写 0x20004128+0x8c / +0x8d（0x08006DE8 那两个字节）")
for k, i in enumerate(insns):
    if i.mnemonic == 'movw' and ('#0x4100' in i.op_str or '#0x6de8' in i.op_str):
        pass
for i in insns:
    if i.mnemonic.startswith('str') and ('#0x8c]' in i.op_str or '#0x8d]' in i.op_str):
        print(f"   {i.address:#010x}: {i.mnemonic} {i.op_str}")
