# find_desc.py —— 在固件 BIN 中定位 HID 描述符、协议常量、以及可能的震动相关代码/表
import re
import struct

BIN = r"C:\Windows\Firmware\TB14P_GT7868Q_14030522_20240202.BIN"
data = open(BIN, "rb").read()
print("BIN 大小:", len(data), " 56KB 镜像偏移: 0x19ABC")

IMG_OFF = 0x19ABC
img = data[IMG_OFF:]
print("镜像长度:", len(img))

pats = {
    "厂商集合 06 00 FF 09 01 A1 01 85 0E": bytes.fromhex("0600FF0901A101850E"),
    "厂商集合(不带rid) 06 00 FF 09 01 A1 01": bytes.fromhex("0600FF0901A101"),
    "数字化仪触控板 05 0D 09 05 A1 01": bytes.fromhex("050D0905A101"),
    "触觉用法页 06 0E 00": bytes.fromhex("060E00"),
    "触觉强度 09 23": bytes.fromhex("0923"),
    "触觉集合 0E 01": bytes.fromhex("0E01"),
    "单触觉控制器 A1 01 06 0E": bytes.fromhex("A101060E"),
    "报告ID 0x0E (85 0E)": bytes.fromhex("850E"),
    "命令 0E 20": bytes.fromhex("0E20"),
    "HID 描述符标记 05 01 09 02": bytes.fromhex("05010902"),
    "PTP 特征 rid=9 (85 09)": bytes.fromhex("8509"),
}

for name, pat in pats.items():
    hits_all = [m.start() for m in re.finditer(re.escape(pat), data)]
    hits_img = [m.start() for m in re.finditer(re.escape(pat), img)]
    print(f"\n{name}")
    print(f"  整个 BIN: {len(hits_all)} 处 {[hex(h) for h in hits_all[:10]]}")
    print(f"  56KB镜像: {len(hits_img)} 处 {[hex(h) for h in hits_img[:10]]}")

# 16 位/32 位常量搜索（协议地址）
print("\n=== 协议地址常量 (小端 16 位) ===")
for val, nm in ((0x60CC, "CMD_ADDR"), (0x5095, "BL_STATE"), (0x5096, "FLASH_RESULT"),
                (0xC000, "FLASH_BUFFER"), (0x4100, "RAW_STATUS"), (0x452C, "FW_INFO")):
    pat = struct.pack("<H", val)
    hits = [m.start() for m in re.finditer(re.escape(pat), img)]
    print(f"  {nm} 0x{val:04X}: 镜像中 {len(hits)} 处 {[hex(h) for h in hits[:8]]}")

# 32 位大端常量
print("\n=== 协议地址常量 (32 位大端, 工具用) ===")
for val, nm in ((0x60CC, "CMD_ADDR"), (0x452C, "FW_INFO")):
    pat = struct.pack(">I", val)
    hits = [m.start() for m in re.finditer(re.escape(pat), data)]
    print(f"  {nm} 0x{val:08X}: BIN 中 {len(hits)} 处 {[hex(h) for h in hits[:8]]}")

# 镜像里可能的字符串
print("\n=== 镜像内 ASCII 字符串 (>=5) ===")
n = 0
for m in re.finditer(rb"[\x20-\x7E]{5,}", img):
    print(f"  +0x{m.start():05X} (文件 0x{IMG_OFF+m.start():06X}): {m.group().decode('ascii')[:90]}")
    n += 1
    if n > 60:
        print("  ...(截断)")
        break
if n == 0:
    print("  (无)")
