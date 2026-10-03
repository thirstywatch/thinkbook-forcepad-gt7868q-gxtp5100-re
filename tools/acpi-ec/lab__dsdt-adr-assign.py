#!/usr/bin/env python3
# dsdt-adr-assign.py —— 定位 DSDT 里给 ADR0/ADR1 赋值的地方（厂商识别 → 回填 I2C 地址）
#
# 背景：TPAD 子树里 Name(ADR0, Zero) 是 I2C 地址占位，_DSM 用 IICB+ADR0 拼资源描述符。
#       那 ADR0 必然在别处被写入 —— 写入点就是"判断插的是哪家触控板"的地方。
#       弄懂它，才知道换 X9-15 模组为什么 Code 10。
import os, re, struct

DSDT = r"<WORKSPACE>"
b = open(DSDT, "rb").read()
print(f"DSDT {len(b)} B")

def hexdump(lo, hi, label=""):
    print(f"\n--- {label} 0x{lo:X}..0x{hi:X} ---")
    for o in range(lo, hi, 16):
        seg = b[o:o+16]
        txt = "".join(chr(x) if 32 <= x < 127 else "." for x in seg)
        print(f"  0x{o:06X}: " + " ".join(f"{x:02X}" for x in seg) + "  " + txt)

# 1) ADR0/ADR1 全部出现位置
for name in (b"ADR0", b"ADR1", b"IICB"):
    pos = []
    i = 0
    while True:
        i = b.find(name, i)
        if i < 0:
            break
        pos.append(i)
        i += 1
    print(f"\n{name.decode()} 共 {len(pos)} 处: " + " ".join(f"0x{p:X}" for p in pos))

# 2) 找 IICB 的【定义】：NameOp(08) / MethodOp(14) / ScopeOp(10) / DeviceOp(5B82) 后跟 IICB
print("\n=== IICB 的定义点（前面是 08/14/10/5B82 等操作符）===")
i = 0
while True:
    i = b.find(b"IICB", i)
    if i < 0:
        break
    prev = b[i-1] if i > 0 else 0
    kind = {0x08: "Name", 0x14: "Method", 0x10: "Scope", 0x82: "Device", 0x15: "External"}.get(prev)
    if kind:
        ctx = b[max(0,i-8):i+12]
        print(f"  0x{i:X}  prev=0x{prev:02X} ({kind})  ctx: " + " ".join(f"{x:02X}" for x in ctx))
    i += 1

# 3) 给 ADR0 赋值的模式：StoreOp(0x70) 源...目标；目标是 NameString ADR0 时，StoreOp 后跟源对象再跟 ADR0
print("\n=== 疑似给 ADR0/ADR1 赋值（Store 族操作符 + 目标为 ADR0/ADR1）===")
for name in (b"ADR0", b"ADR1"):
    i = 0
    while True:
        i = b.find(name, i)
        if i < 0:
            break
        # 往前找最近的 70/71/72/73/74/77/78/79/7A/7B/7C/7D (Store 族) 或 a0/0x0d
        lo = max(0, i-24)
        win = b[lo:i]
        op = None
        for k in range(len(win)-1, -1, -1):
            if win[k] in (0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0xA0):
                op = (lo+k, win[k])
                break
        tag = f"Store族 0x{op[1]:02X} @0x{op[0]:X}" if op else "（前面 24B 内无 Store 族）"
        print(f"  0x{i:X}  <- {tag}   上下文: " + " ".join(f"{x:02X}" for x in b[max(0,i-16):i+8]))

# 4) 重点反汇编：那几处成对出现的 ADR0/ADR1 区域
for lo in (0x116E0, 0x27C80, 0x28170, 0x28660):
    hexdump(lo, lo + 0xA0, "ADR 赋值区")
