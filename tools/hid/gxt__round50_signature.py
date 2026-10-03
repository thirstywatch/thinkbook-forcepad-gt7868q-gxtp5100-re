#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND50: 修正模型 —— 0x1BA7C 到底把"值"写到哪?
之前模型: 0x1BA7C(buf, value) -> flash[0x1800] = value
新怀疑:   0x1BA7C(r0=buf, r1=value) 内部:
             r2 = value
             r1 = 0x1800        <-- ★ 这个 0x1800 是 len?? 还是 addr?
             bl 0x1B874         0x1B874(src, addr, len)
          即调用形式是 0x1B874(r0, 0x1800, r2)
          parameter1 = r0 (原样传) = src
          parameter2 = 0x1800       = addr  <-- 那 addr=0x1800 就对
          parameter3 = r2 = value   = len   <-- 但 len 是个"值"?? 不合理

  重新读 0x1B874 签名 (round48 输出):
      str.w r0, [sp,#0x418]   ; arg0
      str.w r1, [sp,#0x414]   ; arg1
      strh.w r2, [sp,#0x412]  ; arg2  <-- 半字! 所以 arg2 是 len
      ...
      ldr r0,[sp,#0x414] ; ldrh r1,[sp,#0x412] ; add r0,r1 ; cmp #0x7000   ; arg1+arg2
      ... add r0, 0x08019000 -> 目标地址 = 0x08019000 + arg1
  => 0x1B874(src=arg0, off=arg1, len=arg2)  ---- 确认

  那 0x1BA7C 调用 0x1B874(r0, 0x1800, r2) 中:
      arg0 = r0  = 进入时的第一个参数
      arg1 = 0x1800
      arg2 = r2  = 进入时的第二个参数(低字节)
  => 用户态语义: 0x1BA7C(p_buf, len) 把 p_buf[0..len) 写到 flash 偏移 0x1800
  => ★ 那 "写单字节" 的判断是错的! 它是 "写一块数据到 0x1800"

  必须看 caller 0x22E60 传了什么, 才能定 r2(len) 和 r0(buf)
"""
import os, glob
from capstone import *

g = glob.glob(r"<HOME>\**\TB14P_GT7868Q*.BIN", recursive=True)
FW = g[0]
print("FW =", FW)
D = open(FW, "rb").read()
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB + CS_MODE_MCLASS)

def dis(off, n, title=""):
    print(f"\n===== {title} @ 0x{off:X} =====")
    for i in md.disasm(D[off:off+n*4], BASE+off):
        print(f"  0x{i.address:08X}  {i.bytes.hex():<10} {i.mnemonic:<8} {i.op_str}")

# 关键: 0x22E60 是 cmd 0x3200 的 case, 看它怎么准备 r0/r1
dis(0x22E00, 60, "dispatcher case: 0x3200 区域 (含 0x22E04 cmd0x1700 / 0x22E60)")

# 0x1ADD8 / 0x1ADFC 是协议解析里的分支, 看 0x3800 与 0x1800 的对称性
dis(0x1ADB0, 45, "协议解析分支 0x1ADD8(写0x3800) / 0x1ADFC(读0x1800)")
