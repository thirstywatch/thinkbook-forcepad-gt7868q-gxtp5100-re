# callgraph2.py —— 熵图 + 通过 movw/movt 立即数追函数指针（间接调用链）
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct, math

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
IMG = 0x19ABC
BASE = 0x08000000
img = data[IMG:]
END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.skipdata = True
insns = list(md.disasm(bytes(img), BASE))

print("=== 熵图 (4KB 块) ===")
for off in range(0, len(img), 4096):
    blk = img[off:off + 4096]
    if not blk:
        break
    cnt = [0] * 256
    for b in blk:
        cnt[b] += 1
    H = -sum((c / len(blk)) * math.log2(c / len(blk)) for c in cnt if c)
    nz = sum(1 for b in blk if b)
    tag = ""
    if H > 7.5:
        tag = "  <== 高熵(加密/压缩?)"
    elif H < 1.0:
        tag = "  (几乎全零)"
    print(f"  0x{BASE+off:08X}-0x{BASE+off+len(blk):08X}  H={H:5.2f}  非零={nz:5d}{tag}")

# 建立 movw/movt 立即数表
print("\n=== 建立 movw/movt 立即数索引 ===")
movwt = []   # (site, value)
i = 0
while i < len(insns) - 1:
    a, b = insns[i], insns[i + 1]
    if a.mnemonic == "movw" and b.mnemonic == "movt" and a.op_str.startswith("r") and b.op_str.startswith("r"):
        try:
            ra, va = a.op_str.split(", #")
            rb, vb = b.op_str.split(", #")
            if ra == rb:
                movwt.append((a.address, (int(vb, 16) << 16) | int(va, 16)))
        except ValueError:
            pass
    i += 1
print(f"  共 {len(movwt)} 条 movw/movt 对")


def enclosing(addr):
    # 用 push{...,lr} 且其后 8 字节内没有 pop 的最近位置近似
    cands = [x.address for x in insns if x.address <= addr and x.mnemonic == "push" and "lr" in x.op_str]
    return cands[-1] if cands else None


print("\n=== 关键函数作为立即数出现的位置（即间接调用/注册点）===")
seeds = {
    0x08009750: "LRA TIM3 运行时配置",
    0x08008FE8: "LRA/TIM2 初始化",
    0x08008704: "PWM 配置",
    0x08003B68: "I2C/前端初始化",
    0x08008A4C: "I2C ISR 调用者",
    0x0800AA20: "疑似 I2C 事务/上层",
    0x0800AD80: "(在被调用函数内部)",
    0x0800D6F4: "波形回调(数据区?)",
    0x0800F0B4: "模块A handler",
    0x08005DE0: "模块B handler",
}
for fn, nm in seeds.items():
    for bit in (fn, fn | 1):
        hits = [site for site, val in movwt if val == bit]
        if hits:
            print(f"  {nm} 0x{fn:08X} (|1={bit&1}) 出现在: {[hex(h) for h in hits[:6]]}")
            for h in hits[:3]:
                e = enclosing(h)
                print(f"      站点 0x{h:08X} 所在函数 ~0x{e:08X}" if e else f"      站点 0x{h:08X}")
            break
    else:
        print(f"  {nm} 0x{fn:08X}: 未以立即数出现")
