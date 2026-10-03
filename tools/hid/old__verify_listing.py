"""独立校验（v2）：在 asm.txt 给出的每个地址上用 capstone 解码，
检查「指令长度 == 到下一条的间距」且「助记符一致」。

这是对 asm.txt 是否为正确线性反汇编的直接检验。
"""
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "touchpad_GT7868Q_fw.bin")
ASM = os.path.join(HERE, "touchpad_TF100A_thumb.asm.txt")
REGION_OFF, REGION_ADDR = 0x19ABC, 0x08005000

data = open(BIN, "rb").read()

rows = []
for l in open(ASM, encoding="utf-8"):
    p = l.rstrip().split(None, 2)
    if len(p) < 2:
        continue
    try:
        pc = int(p[0], 16)
    except ValueError:
        continue
    rows.append((pc, p[1], p[2] if len(p) > 2 else ""))
rows.sort()

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.detail = False

ALIAS = {"ldr.w": "ldr", "ldrb.w": "ldrb", "ldrh.w": "ldrh", "str.w": "str",
         "strb.w": "strb", "strh.w": "strh", "pop.w": "pop", "push.w": "push",
         "bl.w": "bl", "b.w": "b", "add.w": "add", "sub.w": "sub", "mov.w": "mov",
         "cmp.w": "cmp", "orr.w": "orr", "and.w": "and", "bic.w": "bic",
         "ldrsh.w": "ldrsh", "ldrsb.w": "ldrsb", "adds.w": "adds", "subs.w": "subs",
         "strd": "strd", "adr.w": "adr", "mvn.w": "mvn", "rsb.w": "rsb", "mla": "mla"}

n = len(rows)
undecodable = []
sizemismatch = []
mnemismatch = []
for i, (pc, mn, ops) in enumerate(rows):
    nxt = rows[i + 1][0] if i + 1 < n else pc + 2
    off = pc - REGION_ADDR + REGION_OFF
    chunk = data[off:off + 4]
    got = list(md.disasm(chunk, pc, count=1))
    if not got:
        undecodable.append((pc, mn, ops))
        continue
    ins = got[0]
    if ins.size != nxt - pc:
        sizemismatch.append((pc, mn, ins.size, nxt - pc))
        continue
    cm = ALIAS.get(ins.mnemonic, ins.mnemonic)
    lm = ALIAS.get(mn, mn)
    if cm != lm:
        mnemismatch.append((pc, mn, lm, cm, ins.mnemonic))

print("asm.txt 共 %d 条" % n)
print("capstone 无法解码 : %d 条" % len(undecodable))
print("指令长度与间距不符: %d 条" % len(sizemismatch))
print("助记符不一致      : %d 条" % len(mnemismatch))
for tag, arr in (("UNDECODE", undecodable), ("SIZE", sizemismatch), ("MNEM", mnemismatch)):
    for x in arr[:15]:
        print("   %-9s %s" % (tag, x))

lo, hi = 0x0800894C, 0x08008C32
inblk = [r for r in rows if lo <= r[0] <= hi]
print("\n★ I2C 驱动块 0x%08X-0x%08X 共 %d 条" % (lo, hi, len(inblk)))
b1 = [x for x in undecodable if lo <= x[0] <= hi]
b2 = [x for x in sizemismatch if lo <= x[0] <= hi]
b3 = [x for x in mnemismatch if lo <= x[0] <= hi]
print("   其中 无法解码 %d / 长度不符 %d / 助记符不符 %d" % (len(b1), len(b2), len(b3)))

# 向量表区域单独看
vt = [r for r in rows if 0x08005000 <= r[0] < 0x08005180]
print("★ 向量表区 0x08005000-0x0800517F 共 %d 条（线性反汇编会把数据当指令，属预期）" % len(vt))

# 全镜像里"capstone 解码长度与 asm.txt 间距一致"的比例
ok = n - len(undecodable) - len(sizemismatch)
print("\n结论：asm.txt 的 %d/%d = %.2f%% 的条目在 capstone 下长度自洽" % (ok, n, 100.0 * ok / n))
