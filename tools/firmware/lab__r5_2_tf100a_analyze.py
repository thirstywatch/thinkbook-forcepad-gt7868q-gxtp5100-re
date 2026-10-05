# -*- coding: utf-8 -*-
"""R5-2: TF100A(载荷B) 自带 mini-反汇编扫描：movw/movt 常量 + literal pool → 完整外设图 + I2C 主/从判定"""
import struct, collections

O = open('orig_TB14P.bin', 'rb').read()
CODE = O[0x19ABC:0x19ABC + (0x2775C-0x19ABC)]     # 载荷B 代码区
BASE = 0x08005000
print(f"载荷B 代码区 {len(CODE)} B, 基址 {BASE:#x}")

def u8(a): 
    return CODE[a-BASE] if 0 <= a-BASE < len(CODE) else 0
def u16(a):
    if a-BASE < 0 or a-BASE+2 > len(CODE): return 0
    return struct.unpack_from('<H', CODE, a-BASE)[0]
def u32(a):
    if a-BASE < 0 or a-BASE+4 > len(CODE): return 0
    return struct.unpack_from('<I', CODE, a-BASE)[0]

# ---------- 1) movw/movt + ldr literal ----------
consts = collections.Counter()
src = collections.defaultdict(list)
pend = {}
end = BASE + len(CODE)
a = BASE
while a < end - 4:
    h = u16(a)
    hi, lo = h >> 8, h & 0xFF
    kind = None
    # movw rD, #imm16 : 11110 i 10 0100 imm4 | 0 imm3 Rd imm8   -> 0xF240/0xF640
    if (h & 0xFBF0) == 0xF240:
        rd = (h >> 8) & 0xF
        imm4 = u16(a) & 0xF
        imm3 = (u16(a+2) >> 12) & 0x7
        imm8 = u16(a+2) & 0xFF
        i = (u16(a) >> 10) & 1
        val = (i << 11) | (imm4 << 8) | (imm3 << 8) | imm8
        val = (imm4 << 12) | (i << 11) | (imm3 << 8) | imm8
        pend[rd] = val; a += 4; continue
    # movt rD, #imm16 : 11110 i 10 1100 imm4 | 0 imm3 Rd imm8 -> 0xF2C0/0xF6C0
    if (h & 0xFBF0) == 0xF2C0:
        rd = (h >> 8) & 0xF
        imm4 = u16(a) & 0xF
        imm3 = (u16(a+2) >> 12) & 0x7
        imm8 = u16(a+2) & 0xFF
        i = (u16(a) >> 10) & 1
        val = (imm4 << 12) | (i << 11) | (imm3 << 8) | imm8
        if rd in pend:
            full = (val << 16) | pend.pop(rd)
            consts[full] += 1; src[full].append(a)
        a += 4; continue
    # ldr rD, [pc, #imm] : 01001 Rt imm8  -> 0x48..0x4F
    if (h & 0xF800) == 0x4800:
        rt = (h >> 8) & 7; imm = h & 0xFF
        pcv = (a + 4) & ~3
        lit = u32(pcv + imm*4)
        consts[lit] += 1; src[lit].append(a)
        a += 2; continue
    a += 2

print("\n" + "=" * 96)
print("### 1 ★ TF100A 全部 32 位常量（按用途分类）")
print("=" * 96)
def cls(v):
    if 0x40000000 <= v < 0x40030000: return "APB/AHB 外设"
    if 0xE0000000 <= v < 0xE0100000: return "Cortex-M 系统"
    if 0x08000000 <= v < 0x08020000: return "flash 内"
    if 0x20000000 <= v < 0x20010000: return "SRAM 内"
    return "常量/其他"
byc = collections.defaultdict(list)
for v, n in consts.items():
    byc[cls(v)].append((v, n))
for k in ("APB/AHB 外设", "Cortex-M 系统"):
    print(f"\n  --- {k} ---")
    for v, n in sorted(byc[k], key=lambda t: -t[1]):
        print(f"    {v:#010x} ×{n:<3}  首现 @{src[v][0]:#010x}")
print(f"\n  外设常量总数 {len(byc['APB/AHB 外设'])}, 系统 {len(byc['Cortex-M 系统'])}")

# ---------- 2) I2C 主/从判定 ----------
print("\n" + "=" * 96)
print("### 2 ★ I2C 角色判定：扫所有 [基址+偏移] 访问，看是否写 OAR1(=从机) / DR(=传输)")
print("=" * 96)
I2C = {0x40005400: "I2C1", 0x40005800: "I2C2"}
REG = {0x00: "CR1", 0x04: "CR2", 0x08: "OAR1★从机地址", 0x0C: "OAR2",
       0x10: "DR★数据", 0x14: "SR1", 0x18: "SR2", 0x1C: "CCR(时钟)", 0x20: "TRISE"}
# 找 movw+movt 得到 I2C 基址的寄存器，然后在附近窗口内找 [reg,#off]
i2cregs = {}
for v, addrs in src.items():
    if v in I2C:
        for ad in addrs:
            # 找紧随其后的寄存器号：从反汇编重建太麻烦，改成直接扫 [任何 reg,#0..0x20]
            pass
print("  用窗口法：I2C 基址出现点附近 ±40 字节内的 str/ldr [rX,#0..0x20]")
found = []
for base, name in I2C.items():
    for ad in src.get(base, []):
        for w in range(ad, ad + 48, 2):
            h = u16(w)
            # str rT,[rN,#imm]  0110 000 imm5 rN rT  ->0x6000 ; ldr 0x6800
            if (h & 0xF800) in (0x6000, 0x6800) and (h & 0x0400) == 0:
                imm = (h >> 6) & 0x1F
                rn = (h >> 3) & 7; rt = h & 7
                mn = "str" if (h & 0xF800) == 0x6000 else "ldr"
                found.append((name, ad, w, mn, rn, rt, imm))
for name, ad, w, mn, rn, rt, imm in found[:80]:
    tag = REG.get(imm, "")
    print(f"  {name} 基址@{ad:#010x} → {w:#010x} {mn} r{rt},[r{rn},#{imm:#x}]  {tag}")
print(f"  命中 {len(found)} 处")

# ---------- 3) 关键字面量：0x2C/0x58/0x5A/0xB4 ----------
print("\n" + "=" * 96)
print("### 3 ★ 关键字面量出现点（找 I2C 从地址/AW86927 地址的邻居）")
print("=" * 96)
for target, why in ((0x2C, "TF100A 自身从地址?"), (0x58, "0x2C<<1"), (0x5A, "AW86927"),
                    (0xB4, "0x5A<<1"), (0xAA, "ISP_CMD_FLASH"), (0x55, "ISP_CMD_PREPARE"),
                    (0xDD, "ISP_CHECK_ERR"), (0xBB, "ISP_OK"), (0xCC, "ISP_ERR")):
    hs = [v for v in (u32(x) for x in range(BASE, end-4, 2)) if v == target]
    hits = src.get(target, [])
    print(f"  {target:#04x} ({why:<18}) 作为常量/字面量出现 {len(hits)} 次: "
          f"{[hex(x) for x in hits[:8]]}")
