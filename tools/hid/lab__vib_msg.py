# -*- coding: utf-8 -*-
"""追踪命令分发器 0x080091C0 的消息结构 0x20004134 / 类型字节 0x20004238。
问：这个结构是"主机 HID 报文"还是"配置记录"？谁写它的类型字节？调用点是否在循环里？
"""
import re, bisect, capstone

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
data = open(BIN, 'rb').read()[OFF:OFF + LEN]

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.skipdata = True
insns = list(md.disasm(data, BASE))
addr = [i.address for i in insns]


def dis(a, n=48, tag=""):
    k = bisect.bisect_left(addr, a)
    print(f"\n===== {tag} @ {a:#010x} ({n} 条) =====")
    for i in insns[k:k + n]:
        print(f"{i.address:#010x}: {i.mnemonic:9s} {i.op_str}")


def imms(op):
    out = []
    for x in re.findall(r'#(-?0x[0-9a-fA-F]+|-?\d+)', op):
        try:
            out.append(int(x, 0) & 0xffffffff)
        except ValueError:
            pass
    return out


print("### 1. 序列器 0x0800AD24 起（找循环结构 + 分发器调用点 0x0800ADFA）")
dis(0x0800AD24, 90, "序列器")

print("\n\n### 2. 谁 bl 到 0x080091C0")
hit = 0
for i in insns:
    if i.mnemonic in ('bl', 'blx') and '0x80091c0' in i.op_str.lower():
        print(f"  {i.address:#010x}: {i.mnemonic} {i.op_str}")
        hit += 1
print(f"  → 共 {hit} 处")

print("\n\n### 3. movw 立即数命中 {0x4128,0x4134,0x4234,0x4238,0x423c} 的站点")
want = {0x4128, 0x4134, 0x4234, 0x4238, 0x423c}
n = 0
for k, i in enumerate(insns):
    if i.mnemonic == 'movw':
        v = imms(i.op_str)
        if v and (v[0] & 0xffff) in want:
            n += 1
            print(f"\n>>> {i.address:#010x}: movw {i.op_str}")
            for j in insns[k:k + 7]:
                print(f"    {j.address:#010x}: {j.mnemonic:9s} {j.op_str}")
print(f"  → 共 {n} 处")

print("\n\n### 4. 谁写 [rX, #0x104]（类型字节字段）")
n = 0
for i in insns:
    if i.mnemonic in ('strb', 'strb.w', 'strh', 'strh.w', 'str', 'str.w') and '#0x104]' in i.op_str:
        n += 1
        k = bisect.bisect_left(addr, i.address)
        print(f"\n>>> {i.address:#010x}: {i.mnemonic} {i.op_str}")
        for j in insns[max(0, k - 8):k + 4]:
            print(f"    {j.address:#010x}: {j.mnemonic:9s} {j.op_str}")
print(f"  → 共 {n} 处")

print("\n\n### 5. 谁读 [rX, #0x104] / [rX, #0x108]")
n = 0
for i in insns:
    if i.mnemonic.startswith('ldr') and ('#0x104]' in i.op_str or '#0x108]' in i.op_str):
        n += 1
        print(f"  {i.address:#010x}: {i.mnemonic} {i.op_str}")
print(f"  → 共 {n} 处")
