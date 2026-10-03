# -*- coding: utf-8 -*-
"""B03. 修正判据: capstone.disasm() 遇无效指令会 *停止*，导致统计偏差。
改用 disasm_lite 逐条尝试 + 无效则前进 2 字节（滑动扫描），得到无偏统计。
同时输出：非法指令密度（在真代码里应极低，数据里应很高）—— 但先标定。
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_fw import *
from capstone import *
from capstone.arm import *

FW = load(); N = len(FW)

def slide_scan(buf, base, maxsteps=400000):
    """滑动解码：不因无效指令停止。返回统计。"""
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    i = 0; L = len(buf)
    n_ok = 0; n_bad = 0
    wide = 0
    brs = []          # (addr, size, mnem, target)
    imms = []
    while i < L and (n_ok + n_bad) < maxsteps:
        chunk = buf[i:i+16]
        got = None
        for ins in md.disasm(chunk, base + i):
            got = ins; break
        if got is None:
            n_bad += 1
            i += 2
            continue
        n_ok += 1
        if got.size == 4: wide += 1
        m = got.mnemonic
        tgt = None
        for op in got.operands:
            if op.type == ARM_OP_IMM:
                imms.append(op.imm)
                if m.startswith("b") or m in ("cbz","cbnz"):
                    tgt = op.imm
        if m.startswith("b") or m in ("cbz","cbnz"):
            brs.append((base+i, got.size, m, tgt))
        i += got.size
    return dict(n_ok=n_ok, n_bad=n_bad,
                bad_rate=n_bad/(n_ok+n_bad) if (n_ok+n_bad) else 0,
                wide=wide/n_ok if n_ok else 0,
                bytes_consumed=i,
                brs=brs, imms=imms)

def summarize(tag, buf, base):
    r = slide_scan(buf, base)
    lo, hi = base, base + len(buf)
    brs = r["brs"]
    inb = sum(1 for a, s, m, t in brs if t is not None and lo <= t < hi)
    bl = [b for b in brs if b[2] == "bl"]
    blin = sum(1 for a, s, m, t in bl if t is not None and lo <= t < hi)
    back = sum(1 for a, s, m, t in brs if t is not None and t < a)
    fam = {"0x40000000外设": 0, "0x20000000RAM": 0, "0x08000000FLASH": 0, "0x00000000低区": 0}
    for t in r["imms"]:
        if 0x40000000 <= t < 0x60000000: fam["0x40000000外设"] += 1
        elif 0x20000000 <= t < 0x20080000: fam["0x20000000RAM"] += 1
        elif 0x08000000 <= t < 0x09000000: fam["0x08000000FLASH"] += 1
        elif t < 0x00100000: fam["0x00000000低区"] += 1
    nb = max(1, len(brs))
    print(f"  {tag:22s} ok={r['n_ok']:>5d} bad={r['n_bad']:>4d} 非法率={r['bad_rate']:.4f} "
          f"wide={r['wide']:.3f} 分支={len(brs):>4d} 区内率={inb/nb:.3f} "
          f"bl={len(bl):>4d} bl区内率={(blin/len(bl)) if bl else 0:.3f} 回边率={back/nb:.3f}")
    print(f"  {'':22s} 立即数={len(r['imms']):>5d} 家族={fam}")
    return r

print("=" * 104)
print("B03-a. 标定（滑动扫描，无偏）")
print("=" * 104)
rng = random.Random(7)
func = bytes.fromhex(
    "b5f0" "4d0a" "2400" "f04f26ff" "1c60" "d1fc" "f000f80e" "bd0f" "0000")
real_code = (func * 80)[:1024]
# 再构造一段更真实的：正确对齐的 ldr literal + bl 目标在代码内
blk = bytes()
for k in range(40):
    blk += bytes.fromhex("b5f0")                 # push {r4-r7,lr}
    blk += bytes.fromhex("4804")                 # ldr r0,[pc,#16]
    blk += bytes.fromhex("6801")                 # ldr r1,[r0,#0]
    blk += bytes.fromhex("2900")                 # cmp r1,#0
    blk += bytes.fromhex("d001")                 # beq +2  -> forward
    blk += bytes.fromhex("f7ff ffe7")            # bl -0x32 -> back
    blk += bytes.fromhex("2001")                 # movs r0,#1
    blk += bytes.fromhex("bdf0")                 # pop {r4-r7,pc}
    blk += bytes.fromhex("0000")                 # literal/pad
real2 = (blk * 8)[:2048]
for lbl, b in [("人造Thumb(v1)", real_code), ("人造Thumb(v2-含对齐bl)", real2),
               ("随机字节", bytes(rng.randrange(256) for _ in range(4096))),
               ("随机16bit字流", b"".join(rng.randrange(65536).to_bytes(2,"little") for _ in range(2048))),
               ("全0x00", b"\x00"*4096), ("全0xFF", b"\xff"*4096),
               ("ASCII", (b"Config data table for touchpad sensor calibration. "*100)[:4096]),
               ("递增", bytes(i%256 for i in range(4096)))]:
    summarize(lbl, b, 0x08000000)

print("\n" + "=" * 104)
print("B03-b. 固件全区段扫描")
print("=" * 104)
segs = [("0x00000", 0x00000), ("0x00800", 0x800), ("0x01000", 0x1000), ("0x01200", 0x1200),
        ("0x01800", 0x1800), ("0x02000", 0x2000), ("0x08000", 0x8000), ("0x0C000", 0xC000),
        ("0x10000", 0x10000), ("0x14000", 0x14000), ("0x18000", 0x18000), ("0x19000", 0x19000),
        ("0x19A00", 0x19A00), ("0x1A000", 0x1A000), ("0x1B000", 0x1B000), ("0x1C000", 0x1C000),
        ("0x1D000", 0x1D000), ("0x1E000", 0x1E000), ("0x1F000", 0x1F000), ("0x20000", 0x20000),
        ("0x21000", 0x21000), ("0x22000", 0x22000), ("0x24000", 0x24000), ("0x25000", 0x25000),
        ("0x26000", 0x26000), ("0x27000", 0x27000)]
for tag, off in segs:
    ln = min(0x1000, N-off)
    summarize(tag, FW[off:off+ln], 0x08000000+off)
