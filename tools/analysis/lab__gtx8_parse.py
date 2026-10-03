# gtx8_parse.py —— 用 Goodix 官方 GTX8 固件格式解析我们的 BIN
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
buf = open(BIN, "rb").read()
print(f"BIN = {len(buf)} 字节")
print("前 32 字节:", buf[:32].hex(" "))

def sum16(b):
    s = 0
    for x in b:
        s = (s + x) & 0xFFFF
    return s

print("\n=== 1) 用校验和约束反推头部 (checksum 覆盖 buf[6 : 6+firmware_size]) ===")
found = False
for size_off, size_end in ((2, 6), (0, 4), (6, 10)):
    for csum_off in (0, 4, 6, 8):
        for endian in ("<", ">"):
            fw_size = struct.unpack_from(endian + "I", buf, size_off)[0]
            if not (1000 < fw_size < len(buf)):
                continue
            for cend in ("<", ">"):
                if csum_off + 2 > len(buf):
                    continue
                csum = struct.unpack_from(cend + "H", buf, csum_off)[0]
                if sum16(buf[6:6 + fw_size]) == csum:
                    print(f"  ★ 命中: firmware_size@{size_off}({endian})={fw_size}  checksum@{csum_off}({cend})=0x{csum:04X}")
                    found = True
if not found:
    print("  未命中 → 头部字段布局需另行推断")

print("\n=== 2) 假设 payload 从 256 开始，检查 1084 字节块的规律 ===")
print("  buf[0x100:0x110]:", buf[0x100:0x110].hex(" "))
# 找出所有 1084 (=0x43C) 出现的位置
occ = []
i = 0
while True:
    j = buf.find(struct.pack("<I", 1084), i)
    if j < 0:
        break
    occ.append(j)
    i = j + 1
print(f"  小端 1084(0x43C) 出现 {len(occ)} 次, 前 12 个位置: {[hex(x) for x in occ[:12]]}")
if len(occ) > 2:
    gaps = [occ[k+1]-occ[k] for k in range(min(12, len(occ)-1))]
    print(f"  相邻间隔: {gaps}")

print("\n=== 3) 若镜像描述符紧跟在 6 字节头之后，尝试解码前 10 个 ===")
# 猜测: 描述符 = [kind(1)][addr(2)][size(4)] 或 [size(4)][addr(2)][kind(1)] 等
for desc_len in (6, 7, 8):
    print(f"  --- 假设描述符长 {desc_len} ---")
    off = 6
    for k in range(8):
        d = buf[off:off + desc_len]
        if len(d) < desc_len:
            break
        print(f"    [{k}] @0x{off:03X}: {d.hex(' ')}")
        off += desc_len
