# -*- coding: utf-8 -*-
"""B07. ★★★ ARM vs Thumb 终极判定 (这是全项目最关键的一条)。
判据设计: 
  J_align: 若为 Thumb, 任意偶数偏移反汇编都应"看起来合理"(因为指令是 2/4B 对齐)。
           若为 ARM, 只有 4 字节对齐处才合理。
  J_shift: 把起点整体移动 2 字节后重新解码的可解析率变化:
           Thumb: 移动 2 仍高(都是合法起点) -> 低区分度
           ARM  : 移动 2 后应该变差(因为破坏了 4B 对齐)
  J_illegal: 非法指令率 (ARM 模式 vs Thumb 模式 各自计算)
关键: 先在已知样本上标定 "ARM 代码在 ARM 模式/Thumb 模式" 与 "Thumb 代码在两种模式"。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *
FW = load(); N = len(FW)

def scan(buf, base, mode, align=1):
    md = Cs(CS_ARCH_ARM, mode)
    i = 0; ok = 0; bad = 0
    L = len(buf)
    while i < L and ok + bad < 6000:
        got = None
        for ins in md.disasm(buf[i:i+16], base+i):
            got = ins; break
        if got is None:
            bad += 1; i += align; continue
        ok += 1; i += got.size
    return ok, bad, (bad/(ok+bad) if ok+bad else 1.0)

print("=" * 104)
print("B07-a. 标定: 已知 ARM / Thumb 代码在两种模式下的非法率")
print("=" * 104)
# 人造 ARM 代码 (标准 ARM 序言): push {r4-r7,lr} = e92d40f0 ; mov r0,#0 = e3a00000 ; bx lr = e12fff1e
arm_code = (bytes.fromhex("f0402de9") + bytes.fromhex("0000a0e3") + bytes.fromhex("1eff2fe1") +
            bytes.fromhex("f0402de9") + bytes.fromhex("0100a0e3") + bytes.fromhex("1eff2fe1")) * 40
# 人造 Thumb 代码
th_code = (bytes.fromhex("b5f0") + bytes.fromhex("2000") + bytes.fromhex("bd f0".replace(" ","")) +
           bytes.fromhex("b5f0") + bytes.fromhex("2001") + bytes.fromhex("bdf0")) * 40
for tag, b in [("人造ARM代码", arm_code), ("人造Thumb代码", th_code),
               ("随机字节", bytes(__import__("random").Random(1).randrange(256) for _ in range(2048)))]:
    oA, bA, rA = scan(b, 0x1000, CS_MODE_ARM, align=4)
    oT, bT, rT = scan(b, 0x1000, CS_MODE_THUMB, align=2)
    print(f"  {tag:16s} ARM模式: ok={oA:>5d} bad={bA:>4d} 非法率={rA:.4f} | "
          f"Thumb模式: ok={oT:>5d} bad={bT:>4d} 非法率={rT:.4f}")

print("\n" + "=" * 104)
print("B07-b. ★★★ 真实代码区 (0x19850-0x265B8): ARM vs Thumb 对比")
print("=" * 104)
blk = FW[0x19850:0x265B8]
for tag, mode, al in [("ARM 模式 (4B 对齐前进)", CS_MODE_ARM, 4),
                      ("ARM 模式 (2B 对齐前进)", CS_MODE_ARM, 2),
                      ("Thumb 模式 (2B 前进)", CS_MODE_THUMB, 2)]:
    o, b, r = scan(blk, 0x19850, mode, align=al)
    print(f"  {tag:26s} ok={o:>6d} bad={b:>5d} 非法率={r:.4f}")

print("\n" + "=" * 104)
print("B07-c. ★★★ 起点移位实验: 若为 ARM, 只有 %4==0 的起点合理")
print("=" * 104)
print("  (对 0x19850-0x1A000 共 0x7B0 字节, 从不同起点各解 512B, 报非法率)")
for sh in range(0, 8, 2):
    off = 0x19850 + sh
    sub = FW[off:off+0x400]
    for mode, nm, al in [(CS_MODE_ARM, "ARM", 4), (CS_MODE_THUMB, "Thumb", 2)]:
        o, b, r = scan(sub, off, mode, align=al)
        print(f"  起点 0x{off:05X} (&3={off%4}) {nm:5s}: ok={o:>4d} bad={b:>4d} 非法率={r:.4f}")

print("\n" + "=" * 104)
print("B07-d. ★★★ 反汇编对照: 0x19850 处 ARM 模式前 40 条")
print("=" * 104)
mdA = Cs(CS_ARCH_ARM, CS_MODE_ARM)
n = 0
for ins in mdA.disasm(FW[0x19850:0x19950], 0x19850):
    print(f"    0x{ins.address:05X}  {ins.bytes.hex():<10s} {ins.mnemonic:<10s} {ins.op_str}")
    n += 1
    if n >= 40: break

print("\n" + "=" * 104)
print("B07-e. ★★★ Thumb 模式的同一段 (对照)")
print("=" * 104)
mdT = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
n = 0
for ins in mdT.disasm(FW[0x19850:0x19950], 0x19850):
    print(f"    0x{ins.address:05X}  {ins.bytes.hex():<10s} {ins.mnemonic:<10s} {ins.op_str}")
    n += 1
    if n >= 40: break
