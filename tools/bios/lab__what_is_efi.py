"""判断一个 .efi 是不是 UEFI Shell（并识别它来自哪家工具链）。
用法：python what_is_efi.py <file.efi>
"""
import re
import struct
import sys

SUBSYS = {10: "EFI_APPLICATION", 11: "EFI_BOOT_SERVICE_DRIVER",
          12: "EFI_RUNTIME_DRIVER", 13: "EFI_ROM"}

# 每条：(标签, 正则, 命中说明)
MARKERS = [
    ("EDK2 Shell", rb"UEFI (?:Inter)?[Aa]ctive Shell|UEFI Shell", "★ EDK2 的 UEFI Shell"),
    ("Shell 提示符", rb"Shell>", "Shell 提示符字符串"),
    ("Shell 包路径", rb"ShellPkg|ShellBinPkg|MdeShellPkg|EdkShellPkg", "EDK 源码路径"),
    ("EDK 版本串", rb"EDK II|EDK2|TianoCore|EFI Development Kit", "EDK 工具链指纹"),
    ("Shell 内置命令", rb"\bbcfg\b|\bdmem\b|\bmemmap\b|\bdrivers\b|\bdevtree\b|\bconnect\b|\bdisconnect\b", "Shell 内置命令名"),
    ("Shell 变量/协议", rb"ShellProtocol|gEfiShellProtocolGuid|SHELL_ENV|ShellExecute", "Shell 协议引用"),
    ("Insyde/厂商", rb"Insyde|H2OFFT|FlashDevice|Fpt|CrisisRecovery", "厂商刷写工具指纹"),
    ("厂商升级", rb"BIOS Update|Firmware Update|SHELLFLASH|N4CSG", "厂商更新流程指纹"),
]

raw = open(sys.argv[1], "rb").read()
print(f"文件: {sys.argv[1]}  ({len(raw):,} 字节)")

# ---- PE 头 ----
pe = struct.unpack_from("<I", raw, 0x3C)[0]
if raw[pe:pe + 4] != b"PE\0\0":
    print("不是 PE 文件")
    sys.exit(1)
mach = struct.unpack_from("<H", raw, pe + 4)[0]
opt = pe + 24
magic = struct.unpack_from("<H", raw, opt)[0]
subsys = struct.unpack_from("<H", raw, opt + 68)[0]
dirs = opt + (108 if magic == 0x20B else 92)
sec_rva, sec_size = struct.unpack_from("<II", raw, dirs + 8 * 4)  # 安全目录（索引 4）
print(f"Machine   0x{mach:04X}   Magic 0x{magic:04X}   Subsystem {subsys} {SUBSYS.get(subsys, '?')}")
print(f"数字签名  安全目录 RVA=0x{sec_rva:X} 大小={sec_size}"
      f"  {'✅ 已签名' if sec_size else '— 未签名'}")
print()

# ---- 字符串标记 ----
print("标识串扫描：")
for label, pat, note in MARKERS:
    hits = re.findall(pat, raw)
    if hits:
        uniq = []
        for h in hits:
            s = h.decode("ascii", "replace")
            if s not in uniq:
                uniq.append(s)
        print(f"  ✅ {label:14s} x{len(hits):<5d} {note}")
        print(f"     例: {', '.join(uniq[:6])}")
    else:
        print(f"  —  {label:14s} 无")
