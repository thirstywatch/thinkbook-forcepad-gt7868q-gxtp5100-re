# -*- coding: utf-8 -*-
"""第三层：LRA ctx+0x14 到底是死指针，还是被运行时填充的回调槽？
对照：0x20004128 结构里的回调表是被 0x08008A4C 填充、被 I2C1 路径调用的。
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


def is_push(h):
    return (h & 0xFF00) in (0xB400, 0xB500)


def show_ptr(v, note=""):
    """v = 带 Thumb 位或不带的候选函数指针"""
    tgt = v & ~1
    if not (BASE <= tgt < BASE + LEN - 2):
        print(f"  {v:#010x} {note}: 越界")
        return
    h = struct.unpack_from('<H', data, tgt - BASE)[0]
    print(f"  {v:#010x} {note}: 目标 {tgt:#010x} 半字 {h:#06x}  push? {is_push(h)}")


print("### A. 0x08009750 全文（LRA ctx 初始化，看 +0x14 写的是什么）")
dis(0x08009750, 56, "LRA ctx init")

print("\n\n### B. 0x08008A4C 全文（回调注册）")
dis(0x08008A4C, 40, "回调注册")

print("\n\n### C. 回调候选的合法性对照")
for v, note in [(0x0800D6F5, "ctx+0x14 写入值"),
                (0x0800DB39, "结构+0x120"),
                (0x0800DB5D, "结构+0x124"),
                (0x0800DADD, "结构+0x128"),
                (0x0800D629, "TIM3 向量"),
                (0x08008629, "播放例程对照")]:
    show_ptr(v, note)

print("\n\n### D. 全部 movw #0x40d0 站点（谁碰 LRA ctx）")
for k, i in enumerate(insns):
    if i.mnemonic == 'movw' and '#0x40d0' in i.op_str:
        print(f"\n>>> {i.address:#010x}")
        for j in insns[max(0, k - 2):k + 8]:
            print(f"    {j.address:#010x}: {j.mnemonic:9s} {j.op_str}")

print("\n\n### E. 叶函数 0x08008B3A / 0x08008B5C / 0x08008AF0 / 0x08008B04 是否在函数指针表里")
for tgt in (0x08008B3B, 0x08008B3A, 0x08008B5D, 0x08008B5C, 0x08008AF1, 0x08008B05):
    hits = []
    for k in range(0, LEN - 4):
        if struct.unpack_from('<I', data, k)[0] == tgt:
            hits.append(f"{BASE+k:#010x}")
    print(f"  字面量 {tgt:#010x}: {hits if hits else '无'}")

print("\n\n### F. 结构 0x20004250 / 0x20004244 / 0x2000424C 的读写站点")
# 基址 0x20004128，偏移 0x128 / 0x11c / 0x124
for off, nm in ((0x128, "+0x128/0x11c"), (0x11c, "+0x11c"), (0x124, "+0x124/0x118")):
    n = 0
    for i in insns:
        if f'#0x{off:x}]' in i.op_str and i.mnemonic.startswith(('str', 'ldr')):
            n += 1
    print(f"  含 #{off:#x}] 的访存指令: {n} 条")
