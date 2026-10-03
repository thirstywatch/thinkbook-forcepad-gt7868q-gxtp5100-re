# analyze_cap.py —— 静态解析 Lenovo/Goodix UEFI 固件胶囊 (5B11M67497.CAP)
import re
import struct
import sys
import uuid

SRC = r"C:\Windows\System32\DriverStore\FileRepository\5b11m67497.inf_amd64_a6c0ea31b0500e70\5B11M67497.CAP"
data = open(SRC, "rb").read()
print("CAP 大小:", len(data))
print("前 64 字节:", data[:64].hex(" "))

# EFI_CAPSULE_HEADER: GUID(16) HeaderSize(4) Flags(4) CapsuleImageSize(4)
guid = uuid.UUID(bytes_le=data[:16])
hdr_size, flags, img_size = struct.unpack_from("<III", data, 16)
print(f"胶囊 GUID: {guid}")
print(f"HeaderSize={hdr_size} Flags=0x{flags:X} CapsuleImageSize={img_size}")

# 找固件卷头 _FVH (0x5F465648) / FVH
print("\n=== 搜索标记 ===")
markers = {
    b"_FVH": "固件卷头",
    b"MZ": "PE 可执行",
    b"Goodix": "Goodix 字串",
    b"GT7868": "芯片型号",
    b"7868": "7868",
    b"haptic": "haptic",
    b"Haptic": "Haptic",
    b"vibrat": "vibrat",
    b"Vibrat": "Vibrat",
    b"LRA": "LRA",
    b"0x60CC": "0x60CC 文本",
    b"UEFI": "UEFI",
    b"Lenovo": "Lenovo",
}
for pat, name in markers.items():
    hits = [m.start() for m in re.finditer(re.escape(pat), data)]
    print(f"  {name:14s} {pat!r:12s}: {len(hits)} 处 {[hex(h) for h in hits[:8]]}")

# ASCII 字符串（挑可能与协议/工具相关的）
print("\n=== 相关 ASCII 字符串 ===")
kw = re.compile(rb"(?i)(goodix|gt7|haptic|vibrat|lra|touch|firmware|update|flash|i2c|hid|waveform|click|motor|\.efi|\.bin|\.rom)")
seen = 0
for m in re.finditer(rb"[\x20-\x7E]{6,}", data):
    s = m.group()
    if kw.search(s):
        print(f"  0x{m.start():06X}: {s.decode('ascii', 'replace')[:100]}")
        seen += 1
        if seen > 80:
            print("  ... (截断)")
            break
if seen == 0:
    print("  (无匹配)")
