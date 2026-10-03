"""verify-B/xcheck.py — 校验 bin(独立 capstone) 与 asm.txt 是否逐字节对应同一映射"""
import sys, re, struct
sys.path.insert(0, r"<WORKSPACE>")
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"<WORKSPACE>"
ASM = r"<WORKSPACE>"
data = open(BIN, "rb").read()

L = [l for l in open(ASM, encoding="utf-8").read().splitlines() if l.strip()]
rows = []
for l in L:
    p = l.split(None, 2)
    rows.append((int(p[0], 16), p[1], p[2] if len(p) > 2 else ""))
print("asm 行数", len(rows), "首地址 %08X 末地址 %08X" % (rows[0][0], rows[-1][0]))

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.detail = False

# 用 asm 中大量出现的地址反推映射常数：对每个候选 base_off 暴力验证
# 取若干 asm 地址，看其 mnemonic 是否与 bin 在 (addr - 0x08005000 + off) 处解码一致
cands = [0x19ABC]
# 也尝试整个文件作为基址的假设
best = None
for off0 in cands:
    ok = tot = 0
    for a, mn, ops in rows[::97]:
        o = a - 0x08005000 + off0
        if o < 0 or o + 4 > len(data):
            continue
        tot += 1
        got = list(md.disasm(data[o:o+4], a))
        if got and got[0].mnemonic.split('.')[0] == mn.split('.')[0]:
            ok += 1
    print("off0=0x%X  抽样 %d  助记符一致 %d (%.1f%%)" % (off0, tot, ok, 100.0*ok/max(tot,1)))

# 打印几个特例
for a, mn, ops in rows[::997][:14]:
    o = a - 0x08005000 + 0x19ABC
    raw = data[o:o+4]
    got = list(md.disasm(raw, a))
    print("  %08X f%05X raw=%s  asm=%-8s %-22s  capstone=%-8s %s" %
          (a, o, raw.hex(), mn, ops,
           got[0].mnemonic if got else "??", got[0].op_str if got else ""))
