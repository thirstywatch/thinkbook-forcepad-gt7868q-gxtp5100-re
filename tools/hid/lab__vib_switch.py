# vib_switch.py —— 解开 0x080081C8 的 switch，找出通往"播放震动"的 case
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read(); IMG = 0x19ABC; BASE = 0x08000000
img = data[IMG:]; md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
idx = {i.address: k for k, i in enumerate(insns)}

FN = 0x080081C8
PLAY = 0x0800864A

# 函数边界：下一个 push {...,lr} 且其后无 pop 直到函数结束 —— 用简单启发：找 0x08008658 的 pop 之后
k0 = idx[FN]
# 先确定函数结尾：从 FN 起找到第一个 "pop {...,pc}" 之后的地址
end = None
for j in range(k0, len(insns)):
    i = insns[j]
    if i.mnemonic == "pop" and "pc" in i.op_str:
        end = i.address + i.size
        break
print(f"函数 0x{FN:08X} 范围 0x{FN:08X} - 0x{end:08X}  ({(end-FN)//2} 条指令)")

# ① 所有跳进 [PLAY-0x200, PLAY+0x40] 的转移
print("\n① 跳到播放站点附近的转移指令:")
for j in range(k0, len(insns)):
    i = insns[j]
    if i.address >= end: break
    if i.mnemonic.startswith("b") and not i.mnemonic.startswith("bl") and i.op_str.startswith("#"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if PLAY - 0x200 <= v <= PLAY + 0x40:
            print(f"   {i.address:08X}: {i.mnemonic} {i.op_str}   -> 0x{v:08X}")

# ② 全部 cmp + 紧随其后的条件转移（switch 判定）
print("\n② 函数内的 cmp 判定链 (cmp rX,#imm 及其后的条件跳转):")
cases = []
j = k0
while j < len(insns) and insns[j].address < end:
    i = insns[j]
    if i.mnemonic.startswith("cmp") and "#" in i.op_str:
        try: v = int(i.op_str.split("#")[1], 16)
        except (IndexError, ValueError): v = None
        # 后面 1-3 条内找条件跳转
        for t in insns[j+1:j+5]:
            if t.address >= end: break
            if t.mnemonic.startswith("b") and t.op_str.startswith("#") and t.mnemonic != "b":
                try: tgt = int(t.op_str.lstrip("#"), 16)
                except ValueError: break
                cases.append((i.address, v, t.mnemonic, tgt))
                break
            if t.mnemonic in ("bl", "b") or t.mnemonic.startswith("bl"): break
    j += 1
print(f"   共 {len(cases)} 条")
for a, v, m, t in cases:
    vs = f"0x{v:X}" if v is not None else "?"
    print(f"   {a:08X}: cmp #{vs:>6s}   {m:5s} -> 0x{t:08X}")

# ③ 播放站点之前的上下文（它是哪个 case 的产物）
print(f"\n③ 播放站点 0x{PLAY:08X} 前 40 条:")
k = idx[PLAY]
for j in range(max(k0, k - 40), min(k + 12, len(insns))):
    i = insns[j]
    mark = "  <<< 播放" if i.address == PLAY else ""
    print(f"   {i.address:08X}: {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}{mark}")
