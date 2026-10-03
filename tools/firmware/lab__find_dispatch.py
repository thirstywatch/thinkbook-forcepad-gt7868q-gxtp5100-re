# find_dispatch.py —— 反汇编 0E 20 命令常量附近，定位厂商命令分发器
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import re

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True


def disasm(img_off, before=0x40, count=40, label=""):
    start = max(0, img_off - before)
    # 对齐到 2 字节
    start &= ~1
    print(f"\n===== {label}  镜像+0x{img_off:05X} (闪存 0x{BASE+img_off:08X}) =====")
    print("原始字节:", img[img_off - 16:img_off + 16].hex(" "))
    n = 0
    for ins in md.disasm(bytes(img[start:start + 512]), BASE + start):
        mark = " <<<" if abs((ins.address - BASE) - img_off) <= 4 else ""
        print(f"  {ins.address:08X}: {ins.bytes.hex():10s} {ins.mnemonic:8s} {ins.op_str}{mark}")
        n += 1
        if n >= count:
            break


for off in (0x1F16, 0x6ABA, 0x6ADC, 0x8D02, 0x9DB6):
    disasm(off, label="0E 20 常量")

# 搜索命令相关常量（0x10..0x23 的 opcode 可能在分发器里）
print("\n\n=== 全镜像 TBB/TBH 跳转表 (switch 分发器特征) ===")
tbb = []
for m in re.finditer(rb"[\xe8\xe9].", img):
    p = m.start()
    if p % 2 == 0:
        tbb.append(p)
print(f"  候选 {len(tbb)} 处: {[hex(x) for x in tbb[:40]]}")

print("\n=== 镜像中 0E 10 / 0E 11 / 0E 12 / 0E 13 序列 (工具命令表) ===")
for pat, nm in ((bytes.fromhex("0E10"), "switch-to-patch"), (bytes.fromhex("0E11"), "start-update"),
                (bytes.fromhex("0E12"), "load-flash"), (bytes.fromhex("0E13"), "reset"),
                (bytes.fromhex("0E0D"), "0E 0D"), (bytes.fromhex("0E0F"), "0E 0F"),
                (bytes.fromhex("0E21"), "0E 21"), (bytes.fromhex("0E22"), "0E 22"),
                (bytes.fromhex("0E23"), "0E 23"), (bytes.fromhex("0E24"), "0E 24")):
    hits = [m.start() for m in re.finditer(re.escape(pat), img)]
    print(f"  {nm:18s} {pat.hex(' ')}: {len(hits)} 处 {[hex(h) for h in hits[:6]]}")
