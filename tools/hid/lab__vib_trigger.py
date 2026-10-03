# vib_trigger.py —— 找"谁能驱动马达"：物化 0x200040D0 的站点 + 分发器全表
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct, bisect

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]
END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))
idx = {i.address: k for k, i in enumerate(insns)}

starts = set()
for k in range(0, 0x100, 4):
    v = struct.unpack_from("<I", img, k)[0]
    if BASE <= v < END: starts.add(v & ~1)
for i in insns:
    if i.mnemonic in ("bl", "bl.w"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if BASE <= v < END: starts.add(v)
starts = sorted(starts)
def owner(a):
    k = bisect.bisect_right(starts, a) - 1
    return starts[k] if k >= 0 else None

print("="*72)
print("① 所有物化 0x200040D0 (LRA 上下文) 的站点，及随后 12 条指令")
print("="*72)
# 找 movw rX,#0x40d0 后跟 movt rX,#0x2000
regs = {}
sites = []
for i in insns:
    if i.mnemonic == "movw" and i.op_str.startswith("r"):
        try: lo = int(i.op_str.split("#")[1], 16)
        except (IndexError, ValueError): continue
        if lo == 0x40d0:
            regs[i.op_str.split(",")[0]] = i.address
    elif i.mnemonic == "movt" and i.op_str.startswith("r"):
        r = i.op_str.split(",")[0]
        if r in regs:
            try: hi = int(i.op_str.split("#")[1], 16)
            except (IndexError, ValueError): continue
            if hi == 0x2000:
                sites.append((regs[r], i.address, r))
            del regs[r]
print(f"  共 {len(sites)} 处")
for a, b, r in sites:
    print(f"\n  --- 物化点 0x{a:08X}-0x{b:08X}  (reg {r})  所在函数 0x{owner(a):08X} ---")
    k = idx[a]
    for j in range(k, min(k + 14, len(insns))):
        i = insns[j]
        print(f"     {i.address:08X}: {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}")

print("\n\n" + "="*72)
print("② 命令分发器 0x080091C0 的完整比较链")
print("="*72)
k = idx[0x080091C0]
last = None
end = None
j = k
while j < len(insns):
    i = insns[j]
    if j > k and i.address in starts and i.address != 0x080091C0:
        end = i.address
        break
    j += 1
print(f"  函数范围 0x080091C0 - 0x{end:08X}" if end else "  到镜像末尾")
for j in range(k, len(insns)):
    i = insns[j]
    if end and i.address >= end: break
    if i.mnemonic in ("cmp", "cmp.w") and "#" in i.op_str:
        try: v = int(i.op_str.split("#")[1], 16)
        except (IndexError, ValueError): continue
        # 找紧随其后的条件跳转
        tgt = None
        for t in insns[j+1:j+4]:
            if t.mnemonic.startswith("b") and t.op_str.startswith("#"):
                try: tgt = int(t.op_str.lstrip("#"), 16)
                except ValueError: pass
                break
        if v >= 0x100 and tgt:
            print(f"   cmd 0x{v:04X}  @0x{i.address:08X}  ->  0x{tgt:08X}")

print("\n\n" + "="*72)
print("③ 各 handler 里是否调用了 0x08008858 / 0x08008868 / TIM3 / GPIOA")
print("="*72)
def scan_handler(h, n=40):
    if h not in idx:
        print(f"  0x{h:08X}: 不在指令流里"); return
    kk = idx[h]
    calls = []
    for j in range(kk, min(kk + n, len(insns))):
        i = insns[j]
        if j > kk and i.address in starts: break
        if i.mnemonic in ("bl", "bl.w", "blx") and i.op_str.startswith("#"):
            try: v = int(i.op_str.lstrip("#"), 16)
            except ValueError: continue
            calls.append((i.address, v))
    print(f"  0x{h:08X} ({owner(h):08X}) bl -> {[hex(v) for _, v in calls]}")

# 收集本文件①里出现的分发器目标
seen = set()
for j in range(k, len(insns)):
    i = insns[j]
    if end and i.address >= end: break
    if i.mnemonic in ("b", "b.w") and i.op_str.startswith("#"):
        try: v = int(i.op_str.lstrip("#"), 16)
        except ValueError: continue
        if BASE <= v < END and v not in seen:
            seen.add(v)
for h in sorted(seen):
    scan_handler(h)
