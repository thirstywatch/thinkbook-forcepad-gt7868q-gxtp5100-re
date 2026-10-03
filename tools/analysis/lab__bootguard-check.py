#!/usr/bin/env python3
# bootguard-check.py —— 验证 BIOS 是否有签名/Boot Guard 保护
#
# 要验的三件事：
#   ① 是否有 Flash Descriptor（5A A5 F0 0F @0x10）+ $FPT 分区表
#   ② 是否有 Boot Guard 迹象：_BG 标记 · BPM/KM manifest · Intel 签名 GUID · FIT 表
#   ③ Goodix DXE 驱动所在固件卷的属性（是否被签名保护）
#
# 全部只读文件分析，不碰机器。

import os, glob, struct, re

CANDIDATES = [
    # 本机
    r"<WORKSPACE>",
    r"<WORKSPACE>",
    # X9-15
    r"<WORKSPACE>",
    r"<WORKSPACE>",
    r"<WORKSPACE>",
]

# Boot Guard / 固件安全相关标记
MARKERS = {
    "FlashDescriptor 5AA5F00F": bytes.fromhex("5aa5f00f"),
    "$FPT": b"$FPT",
    "BootGuard _BG": b"_BG",
    "BootGuard _BGB": b"_BGB",
    "BPM marker": b"BPM ",
    "KM marker": b"KM  ",
    "FIT pointer marker": bytes.fromhex("5f465654"),   # _FVT
    "Intel ACM": b"ACM",
    "ME region": b"$ME",
    "BIOS region": b"$BIOS",
    "FFS signature": b"_FVH",
    "capsule GUID/ESRT": b"EFI_SYSTEM_RESOURCE_TABLE",
}

for p in CANDIDATES:
    if not os.path.exists(p):
        print(f"[缺失] {p}")
        continue
    b = open(p, "rb").read()
    print("=" * 78)
    print(f"{os.path.basename(p)}   {len(b)} B ({len(b)/1048576:.2f} MB)")
    print("=" * 78)

    # ① Flash Descriptor：签名在 0x10
    fd = b[0x10:0x14]
    print(f"  ① 偏移 0x10 的 4 字节 = {fd.hex()}  {'★ 是 Flash Descriptor 签名 (5A A5 F0 0F)' if fd == bytes.fromhex('5aa5f00f') else '（不是标准 FD 签名）'}")

    # ② 各标记的出现次数
    print("  ② 安全相关标记：")
    for name, pat in MARKERS.items():
        n = b.count(pat)
        if n:
            pos = []
            i = 0
            while len(pos) < 5:
                i = b.find(pat, i)
                if i < 0:
                    break
                pos.append(hex(i))
                i += 1
            print(f"       {name:26} × {n:<6} {pos}")
    print()
