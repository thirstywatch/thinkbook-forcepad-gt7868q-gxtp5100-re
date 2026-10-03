# -*- coding: utf-8 -*-
"""收束验证：① 回调/向量目标处到底是不是代码 ② 低熵洼地是什么 ③ 有多少 bl 打进 0x0800C000+
"""
import bisect, struct, capstone

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
OFF, BASE, LEN = 0x19ABC, 0x08000000, 56480
data = open(BIN, 'rb').read()[OFF:OFF + LEN]
END = BASE + LEN

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.skipdata = True
insns = list(md.disasm(data, BASE))
addr = [i.address for i in insns]


def dis(a, n=14, tag=""):
    k = bisect.bisect_left(addr, a)
    print(f"\n-- {tag} @ {a:#010x} --")
    for i in insns[k:k + n]:
        print(f"   {i.address:#010x}: {i.mnemonic:9s} {i.op_str}")


print("### A. 结构回调 + 向量目标逐个反汇编")
dis(0x0800DB38, 10, "结构+0x120 = 0x0800DB39")
dis(0x0800DB5C, 10, "结构+0x124 = 0x0800DB5D")
dis(0x0800DADC, 10, "结构+0x128 = 0x0800DADD")
dis(0x0800CE7C, 8, "向量 0x0800CE7D")
dis(0x0800CEA0, 8, "向量 0x0800CEA1")
dis(0x0800D628, 8, "TIM3 向量 0x0800D629")
dis(0x0800DEE8, 8, "USART1 向量 0x0800DEE9 [越界]")
dis(0x0800DFE4, 8, "UsageFault 0x0800DFE5 [越界]")

print("\n\n### B. 低熵洼地 0x0800D300-0x0800D700 是什么（按 u32 解读）")
k0 = 0x0800D300 - BASE
for k in range(k0, 0x0800D700 - BASE, 4):
    w = struct.unpack_from('<I', data, k)[0]
    f = struct.unpack_from('<f', data, k)[0]
    tag = f"{f:12.6g}" if 1e-6 < abs(f) < 1e6 else "           -"
    asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in data[k:k + 4])
    print(f"   {BASE+k:#010x}: {w:#010x}  {tag}  {asc}")

print("\n\n### C. 全镜像 bl 目标落在 0x0800C000+ 的统计")
cnt = 0
tgt = {}
for i in insns:
    if i.mnemonic in ('bl', 'blx') and i.op_str.startswith('#0x'):
        try:
            t = int(i.op_str[1:], 16)
        except ValueError:
            continue
        if t >= 0x0800C000:
            cnt += 1
            tgt[t] = tgt.get(t, 0) + 1
print(f"   bl 目标 ≥0x0800C000 的共 {cnt} 处")
for t in sorted(tgt):
    flag = "  ← 越界" if t >= END else ""
    print(f"     → {t:#010x}  ×{tgt[t]}{flag}")

print("\n\n### D. 线性扫描是否把洼地当指令？（洼地内的『指令』起点数）")
n = sum(1 for i in insns if 0x0800D300 <= i.address < 0x0800D700)
print(f"   洼地内 capstone 产出 {n} 条『指令』；若为纯数据，此数无意义（Thumb 密度高）")

print("\n\n### E. 洼地边界处的对齐 / 前后文")
k = 0x0800D2E0 - BASE
print(f"   0x0800D2E0 起 48 字节: {data[k:k+48].hex(' ')}")
k = 0x0800D6F0 - BASE
print(f"   0x0800D6F0 起 32 字节: {data[k:k+32].hex(' ')}")
k = 0x0800D700 - BASE
print(f"   0x0800D700 起 32 字节: {data[k:k+32].hex(' ')}")
