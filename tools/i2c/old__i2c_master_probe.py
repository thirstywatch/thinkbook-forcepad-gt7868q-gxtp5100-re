"""
§五 判据：TF100A 是否发起 I2C 主机传输？

数据源：容器 touchpad_GT7868Q_fw.bin 的 TF100A 明文段
  地址映射（项目已确立）：addr = 0x08005000 + (fileoff - 0x19ABC)
  交叉验证：'TF100A_Test_FW' @ file 0x19ECC == 地址 0x08005410

本脚本只做只读解析，不修改任何固件/设备。
"""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
BIN  = os.path.join(HERE, "touchpad_GT7868Q_fw.bin")
ASM  = os.path.join(HERE, "touchpad_TF100A_thumb.asm.txt")

REGION_OFF = 0x19ABC
REGION_ADDR = 0x08005000

def addr2off(a):
    return a - REGION_ADDR + REGION_OFF

def off2addr(o):
    return o - REGION_OFF + REGION_ADDR

data = open(BIN, "rb").read()
print("container size = %d (0x%X)" % (len(data), len(data)))

# --- 1. 验证映射 ---------------------------------------------------------
probe = data[addr2off(0x08005410):addr2off(0x08005410) + 12]
print("addr 0x08005410 -> %r   (期望 TF100A_Test_FW)" % probe)

# --- 2. dump 向量表 ------------------------------------------------------
VT = 0x08005000
print("\n=== 向量表 @0x%08X (file 0x%X) ===" % (VT, addr2off(VT)))
words = struct.unpack_from("<64I", data, addr2off(VT))
print("  [ 0] initial SP = 0x%08X" % words[0])
for i in range(1, 48):
    a = words[i]
    tag = ""
    if a and (a & 1) and 0x08005000 <= (a & ~1) < 0x08012CA0:
        tag = "code"
    elif a == 0:
        tag = "zero"
    else:
        tag = "?"
    name = ""
    if i == 1: name = "Reset"
    elif i == 2: name = "NMI"
    elif i == 3: name = "HardFault"
    elif i == 11: name = "SVC"
    elif i == 14: name = "PendSV"
    elif i == 15: name = "SysTick"
    elif i >= 16: name = "IRQ%d" % (i - 16)
    print("  [%2d] %-9s = 0x%08X  %s" % (i, name, a, tag))
