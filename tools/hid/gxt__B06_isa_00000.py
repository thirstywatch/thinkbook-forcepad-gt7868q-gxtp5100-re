# -*- coding: utf-8 -*-
"""B06. ★ 0x00000 区段架构判定 (攻击点 B3): 是 8051? Z80? 6502? PIC? 还是数据?
判据: 
  - 对每种架构用 capstone (ARM/AArch64/MIPS/x86 可用) 无法覆盖 8 位机,
    改用 '顺序解码的可解析率' + '指令长度分布' + '操作码直方图集中度'。
  - 8 位机关键: 操作码空间小(256), 真代码的 opcode 直方图应高度集中(少数 opcode 占大头)。
    数据/表格则接近均匀或明显偏向 ASCII。
  - 另: 8051 的 LJMP=0x02, LCALL=0x12, AJMP=0x01/0x21...; Z80 的 0x00=NOP, 0x3E=LD A,n;
    6502 的 0x20=JSR, 0x60=RTS, 0xA9=LDA#; PIC 有 14-bit 字结构。
先用已知样本标定每种判据, 再判真实区。
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from collections import Counter
FW = load(); N = len(FW)

def opcode_concentration(b):
    c = Counter(b)
    top1 = c.most_common(1)[0][1]/len(b)
    top4 = sum(v for _, v in c.most_common(4))/len(b)
    top16 = sum(v for _, v in c.most_common(16))/len(b)
    return top1, top4, top16, len(c)

def print_c(tag, b):
    t1, t4, t16, u = opcode_concentration(b)
    print(f"  {tag:34s} 唯一opcode={u:>3d} top1={t1:.3f} top4={t4:.3f} top16={t16:.3f} "
          f"零占比={b.count(0)/len(b):.3f}")

print("=" * 96)
print("B06-a. 标定: 各架构典型样本的 opcode 集中度")
print("=" * 96)
rng = random.Random(5)
# 8051 典型函数 (真实机器码片段, 从常见 8051 序言构造)
c8051 = bytes.fromhex(
    "758100"   # mov sp,#0x00-ish (mov direct,#imm)
    "787f"     # mov r0,#0x7f
    "e4"       # clr a
    "f6"       # mov @r0,a
    "d8fd"     # djnz r0,-3
    "7400"     # mov a,#0
    "f5"       # mov direct,a
    "900000"   # mov dptr,#0
    "e4"       # clr a
    "93"       # movc a,@a+dptr
    "f0"       # movx @dptr,a
    "a3"       # inc dptr
    "22"       # ret
)
samples = [
    ("8051风格样本", (c8051 * 30)[:512]),
    ("全 Z80 NOP(00)", b"\x00"*512),
    ("Z80样本(常见序言)", bytes.fromhex("f5"+"3e00"+"320000"+"c3"+"0000")*60),
    ("6502样本", bytes.fromhex("a900"+"8d0000"+"jsr".replace("jsr","20")+"0000"+"60")*60),
    ("随机字节", bytes(rng.randrange(256) for _ in range(512))),
    ("ASCII", (b"abcdefghijklmnopqrstuvwxyz0123456789"*20)[:512]),
    ("真 Thumb(0x19850)", FW[0x19850:0x19A50]),
]
for tag, b in samples:
    print_c(tag, b)

print("\n" + "=" * 96)
print("B06-b. 0x00000-0x01200 分 256B 段")
print("=" * 96)
for off in range(0, 0x1200, 256):
    print_c(f"0x{off:05X}-0x{off+256:05X}", FW[off:off+256])

print("\n" + "=" * 96)
print("B06-c. ★ 8051 专用结构判据 (标定 + 实盘)")
print("=" * 96)
def c8051_score(b):
    """8051 特征: 
       - 0x02 (LJMP) / 0x12 (LCALL) 后跟 2 字节目标
       - 0x22 (RET) / 0x32 (RETI)
       - 0xE4/0x74 (CLR A / MOV A,#)
       - 0x75 (MOV direct,#data) 三字节
       统计这些 opcode 的密度
    """
    n = len(b)
    ljmp = b.count(0x02)/n
    lcall = b.count(0x12)/n
    ret = b.count(0x22)/n
    movd = b.count(0x75)/n
    return ljmp, lcall, ret, movd
print("  {'LJMP2':>8} {'LCALL12':>8} {'RET22':>8} {'MOVD75':>8}   (随机期望=0.0039)")
for tag, b in [("8051样本", (c8051*30)[:512]), ("随机", bytes(rng.randrange(256) for _ in range(512))),
               ("0x00000-0x00200", FW[0:0x200]), ("0x00200-0x00600", FW[0x200:0x600]),
               ("0x00600-0x00C00", FW[0x600:0xC00]), ("0x00C00-0x01200", FW[0xC00:0x1200]),
               ("0x19850-0x19A50(真Thumb)", FW[0x19850:0x19A50])]:
    l, c, r, m = c8051_score(b)
    print(f"  {tag:24s} {l:8.4f} {c:8.4f} {r:8.4f} {m:8.4f}")

print("\n" + "=" * 96)
print("B06-d. ★★ 0x00000 区段的真实性质: 找 4 字节记录结构 / 指针表特征")
print("=" * 96)
print("  开头 16 字节: " + " ".join(f"{b:02x}" for b in FW[:16]))
print("  le32 序列 (前 16 个):")
for i in range(16):
    print(f"    [{i:2d}] LE=0x{le32(FW,i*4):08X}  BE=0x{be32(FW,i*4):08X}")
