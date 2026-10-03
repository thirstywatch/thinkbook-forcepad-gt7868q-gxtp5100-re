# -*- coding: utf-8 -*-
"""B02. 更强的架构判据设计。
B01 证明: "伪指令率" 在 capstone Thumb 上无区分度(随机数据也是 0)。
原因: Thumb-1 16-bit 空间几乎被 0xxx-11101 占满，随机 16-bit 字几乎总能解码。

改用结构性判据（对真代码/数据有本质差异）：

J1 分支目标有效性 (BT):
   真代码里 b/bl/bx 的目标地址应落在本区段内且落在 2 字节对齐的指令边界。
   统计 "目标落在当前区段内" 的比例。数据里分支指令稀少且目标随机。
J2 4B 宽指令占比 + 宽指令的合法性:
   Thumb-2 宽指令的首半字必须匹配 11101/11110/11111 模式，其后半字有约束。
J3 顺序解码的"自洽链长":
   从随机起点解码，真代码能连续解码的长度分布 vs 数据。
J4 指令多样性: 真代码 mnemonic 分布有明确的结构(load/store/branch 占大头)，
   数据的 mnemonic 分布是解码器边界的伪影。
J5 ★ 最强判据 —— 分支回边密度 (loop back-edge):
   真代码的函数体里，向前条件跳转(if)和向后跳转(loop)都密集出现。
   用"b<cond> 且目标 < 当前地址" 的密度，和 "bl 目标在区内" 的密度。
J6 ★★ 引用完整性: 真代码里出现的立即数加载(ldr/movw) 指向的地址，
   是否落在已知的固件地址空间(0x08000000 flash 别名 / 0x20000000 RAM / 0x40000000 外设)。
   数据里不会系统性出现这类地址。

先在标定样本上跑，确认有区分度再上真实数据。
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *

FW = load(); N = len(FW)

def structural_metrics(buf, base, label):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    n = 0; nbr = 0; back_edge = 0; fwd_edge = 0
    in_range = 0; bl_in = 0; bl_tot = 0
    wide = 0
    imm_targets = []
    lo = base; hi = base + len(buf)
    try:
        for ins in md.disasm(buf, base):
            n += 1
            if ins.size == 4: wide += 1
            m = ins.mnemonic
            # 立即数目标
            for op in ins.operands:
                if op.type == ARM_OP_IMM:
                    imm_targets.append(op.imm)
            if m.startswith("b") or m in ("cbz","cbnz"):
                tgt = None
                for op in ins.operands:
                    if op.type == ARM_OP_IMM: tgt = op.imm
                if tgt is not None:
                    nbr += 1
                    if lo <= tgt < hi: in_range += 1
                    if m == "bl":
                        bl_tot += 1
                        if lo <= tgt < hi: bl_in += 1
                    if tgt < ins.address: back_edge += 1
                    else: fwd_edge += 1
    except Exception:
        pass
    # 立即数中出现的"外设/flash/RAM 地址"族
    fam = {"0x40000000区":0, "0x20000000区":0, "0x08000000区":0, "0x00000000区":0}
    for t in imm_targets:
        if 0x40000000 <= t < 0x60000000: fam["0x40000000区"] += 1
        elif 0x20000000 <= t < 0x20080000: fam["0x20000000区"] += 1
        elif 0x08000000 <= t < 0x09000000: fam["0x08000000区"] += 1
        elif 0x00000000 <= t < 0x00100000: fam["0x00000000区"] += 1
    r = dict(label=label, n=n, wide=wide/n if n else 0,
             br_r=nbr/n if n else 0,
             inrange=nbr and in_range/nbr or 0,
             back=back_edge/n if n else 0,
             fwd=fwd_edge/n if n else 0,
             bltot=bl_tot, blin=bl_tot and bl_in/bl_tot or 0,
             fam=fam, nimm=len(imm_targets))
    print(f"  {label:30s} n={n:>6d} wide={r['wide']:.3f} br占比={r['br_r']:.3f} "
          f"分支目标在区内={r['inrange']:.3f} bl@{r['bltot']:>4d}/区内率={r['blin']:.3f} "
          f"回边={r['back']:.4f} 立即数总数={r['nimm']}")
    return r

print("=" * 100)
print("B02-a. 标定：结构性判据在已知样本上的表现")
print("=" * 100)
rng = random.Random(7)
# 构造一段"真" Thumb 代码：手写常见序言 + 函数体，重复
func = bytes.fromhex(
    "b5f0"          # push {r4-r7,lr}
    "4d0a"          # ldr r5,[pc,#40]
    "2400"          # movs r4,#0
    "f04f26ff"      # mov.w r6,#0xff00  (wide)
    "1c60"          # adds r0,r4,#1
    "d1fc"          # bne -8     (back edge)
    "f000f80e"      # bl +28     (wide bl)
    "bd0f"          # pop {r0-r3,pc}
    "0000")         # align
real_code = (func * 60)[:1024]
tests = [
    ("人造真 Thumb 代码", real_code),
    ("随机字节", bytes(rng.randrange(256) for _ in range(2048))),
    ("全 0x00", b"\x00"*2048),
    ("全 0xFF", b"\xff"*2048),
    ("ASCII 文本", (b"Config data table for touchpad sensor calibration. "*50)[:2048]),
    ("低熵递增", bytes(i % 256 for i in range(2048))),
    ("随机16bit字流", b"".join(rng.randrange(65536).to_bytes(2, "little") for _ in range(1024))),
]
for lbl, b in tests:
    structural_metrics(b, 0x08000000, lbl)

print("\n" + "=" * 100)
print("B02-b. 固件真实区段 (base 用 0x08000000 试，随后再校准)")
print("=" * 100)
for tag, off, ln in [("0x00000", 0, 0x1200), ("0x01200", 0x1200, 0x2000),
                     ("0x08000", 0x8000, 0x2000), ("0x10000", 0x10000, 0x2000),
                     ("0x19A00", 0x19A00, 0x2000), ("0x1A000", 0x1A000, 0x2000),
                     ("0x1C000", 0x1C000, 0x2000), ("0x1E000", 0x1E000, 0x2000),
                     ("0x20000", 0x20000, 0x2000), ("0x22000", 0x22000, 0x2000),
                     ("0x25000", 0x25000, 0x2000), ("0x27000", 0x27000, 0x75C)]:
    ln = min(ln, N-off)
    structural_metrics(FW[off:off+ln], 0x08000000+off, tag)
