# -*- coding: utf-8 -*-
"""E07. ★★★★ 解码 0x050x010x 系列参数 + 汇总触觉证据。
观察: 传给 GPIO 助手 0x24700/0x2473C 的参数形如 0x050A0108 / 0x05010109 ...
      0x24700 里: ubfx r2,r0,#0x10,#5 -> 引脚号 = bits[20:16]
                  lsrs r2,r0,#0x16    -> 端口号 = bits[31:22]
      对 0x050A0108: bits[20:16] = (0x050A0108 >> 16) & 0x1F = 0x0A = 10
                     bits[31:22] = (0x050A0108 >> 22) & 0x3FF = 0x14 = 20 ... 超范围
      => 需重新拆分。下面用位域枚举法判定。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
FW = load()

VALS = [0x050A0108, 0x05010109, 0x05060109, 0x05040109, 0x05070109]
print("=" * 96)
print("E07-a. 参数位域拆分 (0x24700 用了 bits[20:16] 与 bits[31:22])")
print("=" * 96)
for v in VALS:
    pin = (v >> 16) & 0x1F
    port = (v >> 22) & 0x3FF
    lo = v & 0xFFFF
    print(f"  0x{v:08X}:  bits[20:16]={pin:>3d}  bits[31:22]={port:>4d}  "
          f"低16位=0x{lo:04X}  字节={[f'{b:02x}' for b in v.to_bytes(4,'big')]}")
print("\n  说明: bits[31:22] 多数为 0x00014=20 -> 超 32 位端口范围, 说明 0x24700 不是唯一解释")
print("        但 0x2473C 里用了 bits[21]/[20:16]/[31:22] 同样位域 => 这些参数不是 GPIO 参数")
print("  重新判断: 0x050A0108 更像是 '16位地址 + 16位数据' 或 '字节序列 05 0A 01 08'")

print("\n" + "=" * 96)
print("E07-b. ★★★★ 按 4 字节序列解读 (可能的 I2C 写序列)")
print("=" * 96)
print("  所有出现的 0x050x010x 系参数:")
for v in VALS:
    bs = v.to_bytes(4, "big")
    print(f"    0x{v:08X} -> 字节: {[f'{b:02x}' for b in bs]}   "
          f"或 [lo,hi]: [{bs[2]:02x} {bs[3]:02x}] / {bs[0]:02x} {bs[1]:02x}")

print("\n" + "=" * 96)
print("E07-c. ★★★★ 触觉结论汇总 (全部数字)")
print("=" * 96)
print("  1) 关键词 'AW869'/'86927'/'awinic'/'LRA'/'haptic'/'vibr'/'BEMF'/'motor':")
for k in ["AW869", "86927", "awinic", "AWINIC", "LRA", "haptic", "vibr", "BEMF", "motor",
          "AW86927", "AW87", "trig", "wave"]:
    print(f"     '{k}': {FW.count(k.encode())} 次 (全文件, 大小写敏感)")
print("  2) I2C 从地址 0x5A/0x5B 作为立即数出现在代码区: 0x5A=3 次, 0x5B=0 次 (见 E03-c)")
print("  3) 外设访问中发现 I2C1 @0x40005400 (6 次) 与 I2C1 DR @0x40005410 (2 次)")
print("  4) GPIOA @0x40010800 出现 28 次 (STM32F1 地址!)")
print("  5) 0x050x010x 参数 5 个, 与 I2C1 基址同函数 (0x1D408-0x1D4D6)")
print(f"  6) 固件内嵌字符串 'TF100A_Test_FW' @0x19ECC (构建 2023-11-28 19:10:59)")
print(f"  7) 固件内嵌字符串 'YELSTO' @0x1142, '7868Q' @0x114A")

print("\n" + "=" * 96)
print("E07-d. 0x050x010x 的另一种可能: 它们是 HAL 的 'GPIO_Pin_x | GPIO_Mode...' 掩码")
print("=" * 96)
print("  与 STM32 HAL 常见值比较 (HAL_GPIO_Init 的 GPIO_PIN_x 为 (1<<pin)):")
print("  bits 分析: 0x050A0108")
print(f"    bit0-15  = 0x{0x050A0108 & 0xFFFF:04X}")
print(f"    bit16-19 = 0x{(0x050A0108>>16)&0xF:X}")
print(f"    bit20-21 = 0x{(0x050A0108>>20)&0x3:X}  (很可能=1 -> GPIO_PIN 类)")
print(f"    bit22-31 = 0x{(0x050A0108>>22)&0x3FF:X}")
print("  => 5 个参数的变化位集中在 bit16-19 (A/1/6/4/7) 与 bit24-31 (05)")
print("     一致的解释: 高半字 0x050x = 端口/外设编号, 低半字 0x010x = 位索引")
