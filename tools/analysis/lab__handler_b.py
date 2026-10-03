# handler_b.py —— 反汇编 0x08005DE0 (LRA 初始化注册的事件 handler) 及其调用树
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
BASE = 0x08000000
img = data[0x19ABC:]
END = BASE + len(img)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)


def dis_from(a, n=70):
    off = a - BASE
    if off < 0 or off >= len(img):
        print(f"  (0x{a:08X} 在镜像之外: 镜像范围 0x{BASE:08X}-0x{END:08X})")
        return []
    return list(md.disasm(bytes(img[off:off + n * 4]), a))


def show(a, n=70, title=""):
    print(f"\n===== {title} @0x{a:08X} =====")
    for i in dis_from(a, n):
        print(f"  {i.address:08X}: {i.bytes.hex():10s} {i.mnemonic:8s} {i.op_str}")


def calls(a, n=200):
    out = []
    for i in dis_from(a, n):
        if i.mnemonic.startswith("bl"):
            try:
                out.append((i.address, int(i.op_str.lstrip("#"), 16)))
            except ValueError:
                pass
    return out


show(0x08005DE0, 60, "模块B handler (LRA 初始化注册)")
print("\n调用:")
for s, t in calls(0x08005DE0, 400):
    loc = "镜像内" if BASE <= t < END else "★镜像外(加密区)"
    print(f"  0x{s:08X} -> 0x{t:08X}  {loc}")

# 也看看模块A handler 附近(镜像外)有没有可用的东西——只报告边界
print(f"\n镜像范围: 0x{BASE:08X} - 0x{END:08X}")
print("0x0800F0B4 是否在镜像内:", BASE <= 0x0800F0B4 < END)

# 看看 0x08005DE0 前后是否有别的相关函数（波形相关字符串/表）
print("\n=== 0x08005DE0 附近 0x08005D00-0x08005E40 原始字节 ===")
o = 0x08005D00 - BASE
for k in range(0, 0x140, 16):
    chunk = img[o + k:o + k + 16]
    print(f"  {0x08005D00+k:08X}: {' '.join(f'{b:02X}' for b in chunk)}")
