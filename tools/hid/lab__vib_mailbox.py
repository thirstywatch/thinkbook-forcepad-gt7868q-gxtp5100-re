# vib_mailbox.py — 重新审 39 条命令表：1) 表结构与 handler 清单 2) 每个 handler 碰的内存/外设
#                   3) 是否有越出镜像的 bl（藏进缺失尾部）  4) 是否有 ADC（TF100A 自己读力传感器？）
import re, struct, io
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG_OFF = 0x19ABC
img = data[IMG_OFF:]
BASE = 0x08000000
END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = False
out = io.open(r"<LAB>\touchpad-lab\re\vib_mailbox_out.txt", "w", encoding="utf-8")


def P(*a):
    out.write(" ".join(str(x) for x in a) + "\n")


P("image: off=0x%X len=%d (0x%X) BASE=0x%08X END=0x%08X" % (IMG_OFF, len(img), len(img), BASE, END))


def dis(a, n):
    off = a - BASE
    return list(md.disasm(img[off:off + n * 4], a))


# ---------- 1) 反汇编 dispatcher ----------
P("\n" + "=" * 70)
P("=== dispatcher 0x080091C0 ===")
for i in dis(0x080091C0, 60):
    P("  %08X: %-10s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))

# ---------- 2) 扫描全镜像：找命令表（movw/movt 指向的数据表） ----------
P("\n" + "=" * 70)
P("=== 搜索 0x080091C0 内的 movw/movt 立即数 ===")
for i in dis(0x080091C0, 60):
    if i.mnemonic in ("movw", "movt", "ldr"):
        P("  %08X %-8s %s" % (i.address, i.mnemonic, i.op_str))

# ---------- 3) 定位命令表：在 RAM 里找写表的地方 & 直接在镜像里找 (opcode,handler) 表 ----------
P("\n" + "=" * 70)
P("=== 在镜像中搜 (0x80/0xA0/0xA1, handler) 表 ===")
cand = []
for off in range(0, len(img) - 8, 4):
    op = img[off]
    if op not in (0x80, 0xA0, 0xA1, 0xA2, 0x81, 0x82):
        continue
    h = struct.unpack_from("<I", img, off + 4)[0]
    if BASE <= h < END:
        cand.append((BASE + off, op, h))
P("  候选条目数 = %d" % len(cand))
# 聚簇
clusters = []
for c in cand:
    if clusters and c[0] - clusters[-1][-1][0] <= 16:
        clusters[-1].append(c)
    else:
        clusters.append([c])
for cl in clusters:
    if len(cl) >= 3:
        P("  --- 表 @0x%08X  共 %d 条 ---" % (cl[0][0], len(cl)))
        for a, op, h in cl:
            P("      +0x%02X op=0x%02X -> handler 0x%08X" % (a - cl[0][0], op, h))

out.close()
print("done -> vib_mailbox_out.txt")
