# vib_entry.py — 从精确入口反汇编（不做线性扫描）：TIM3 ISR 0x0800D628 / 播放回调 0x0800D6F4
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
img = open(BIN, "rb").read()[0x19ABC:]
BASE = 0x08000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True

def dump(entry, n, title):
    print("\n===== %s @0x%08X =====" % (title, entry))
    off = entry - BASE
    c = 0
    for i in md.disasm(img[off:off + n * 4], entry):
        print("  %08X: %-10s %s" % (i.address, i.bytes.hex(), i.mnemonic + " " + i.op_str))
        c += 1
        if c >= n:
            break

dump(0x0800D628, 70, "向量 slot45 -> 0x0800D629（TIM3?）")
dump(0x0800D6F4, 60, "触觉回调 ctx+0x14 = 0x0800D6F5")
dump(0x0800DFE4, 40, "缺失尾部：SysTick? 0x0800DFE5")
