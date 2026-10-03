# -*- coding: utf-8 -*-
"""B08. ★★★ 检验假设: 代码区是否被 16-bit 字节交换 (ab -> ba)?
证据: 0x19858 处字节 28 b4. 正确 Thumb "push {r3,r5}" = b4 28 (T1 push = 1011 0100 xxxxxxxx).
      0x1985A 处 75 49; 正确 "ldr r1,[pc,#imm]" T1 = 0100 1 rrr iiiiiiii = 0x49xx
      0x1985C 处 e1 0d; 正确 "lsrs r1,r4,#0x17" = 0000 1 iiiii sss ddd = 0x0d e1
      => 每 16-bit 半字内部字节序被交换!
方法: 对代码区做 16-bit 半字内字节交换, 再反汇编, 比较非法率。
      同时做 32-bit 全字节反转 作为对照。
      判据先在标定样本上验证。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
FW = load(); N = len(FW)

def swap16(b):
    o = bytearray(b)
    for i in range(0, len(o)-1, 2):
        o[i], o[i+1] = o[i+1], o[i]
    return bytes(o)

def scan(buf, base, mode):
    md = Cs(CS_ARCH_ARM, mode)
    i = 0; ok = 0; bad = 0
    while i < len(buf) and ok+bad < 8000:
        g = None
        for ins in md.disasm(buf[i:i+16], base+i):
            g = ins; break
        if g is None: bad += 1; i += 2; continue
        ok += 1; i += g.size
    return ok, bad, (bad/(ok+bad) if ok+bad else 1.0)

print("=" * 100)
print("B08-a. 标定: 交换对已知代码的影响")
print("=" * 100)
th = (bytes.fromhex("b5f0") + bytes.fromhex("2001") + bytes.fromhex("bdf0")) * 60
print(f"  人造Thumb 原样 非法率 = {scan(th,0,CS_MODE_THUMB)[2]:.4f}")
print(f"  人造Thumb swap16 后 非法率 = {scan(swap16(th),0,CS_MODE_THUMB)[2]:.4f}")

print("\n" + "=" * 100)
print("B08-b. ★★★ 真实代码区: 原样 vs swap16 vs 32bit反转")
print("=" * 100)
for lo, hi, tag in [(0x19850, 0x1A000, "0x19850-0x1A000"),
                    (0x1A000, 0x1C000, "0x1A000-0x1C000"),
                    (0x1E000, 0x20000, "0x1E000-0x20000"),
                    (0x25000, 0x26600, "0x25000-0x26600")]:
    blk = FW[lo:hi]
    o1, b1, r1 = scan(blk, lo, CS_MODE_THUMB)
    o2, b2, r2 = scan(swap16(blk), lo, CS_MODE_THUMB)
    # 32-bit 反转
    o3 = bytearray()
    for i in range(0, len(blk)-3, 4):
        o3 += blk[i:i+4][::-1]
    o4, b4, r4 = scan(bytes(o3), lo, CS_MODE_THUMB)
    print(f"  {tag}")
    print(f"      原样      ok={o1:>5d} bad={b1:>4d} 非法率={r1:.4f}")
    print(f"      swap16    ok={o2:>5d} bad={b2:>4d} 非法率={r2:.4f}"
          + ("   <<< 显著更好!" if r2 < r1*0.5 else ("   (更差)" if r2 > r1*1.5 else "")))
    print(f"      32bit反转 ok={o4:>5d} bad={b4:>4d} 非法率={r4:.4f}")

print("\n" + "=" * 100)
print("B08-c. ★★★ 0x19850 起 swap16 后逐条反汇编 (看是否变成干净代码)")
print("=" * 100)
blk = swap16(FW[0x19850:0x19950])
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
for ins in md.disasm(blk, 0x19850):
    print(f"    0x{ins.address:05X}  {ins.bytes.hex():<8s} {ins.mnemonic:<10s} {ins.op_str}")

print("\n" + "=" * 100)
print("B08-d. ★★★ 对照: 原样逐条 (同一段)")
print("=" * 100)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
for ins in md.disasm(FW[0x19850:0x19950], 0x19850):
    print(f"    0x{ins.address:05X}  {ins.bytes.hex():<8s} {ins.mnemonic:<10s} {ins.op_str}")
