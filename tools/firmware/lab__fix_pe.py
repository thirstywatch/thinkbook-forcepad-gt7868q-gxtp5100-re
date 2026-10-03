"""后处理 MSVC 产出的 EFI 镜像，使其更贴近 EDK2/GenFw 的产物。

做两件事：
1. 清掉 IMAGE_FILE_DLL (0x2000) —— MSVC 对 EFI 驱动子系统会自动打上这个标志，
   而 EDK2 的 GenFw 会显式清除它。部分固件的 LoadImage 对此敏感。
2. 打印节表与数据目录摘要，确认没有导入表（UEFI 驱动应为零导入）。

用法：python fix_pe.py TpadAcpiProbe.efi ...
"""
import struct
import sys

IMAGE_FILE_DLL = 0x2000
IMAGE_FILE_EXECUTABLE_IMAGE = 0x0002


def fix(path):
    d = bytearray(open(path, "rb").read())
    pe = struct.unpack_from("<I", d, 0x3C)[0]

    chars_off = pe + 22
    chars = struct.unpack_from("<H", d, chars_off)[0]
    had_dll = bool(chars & IMAGE_FILE_DLL)
    chars &= ~IMAGE_FILE_DLL
    struct.pack_into("<H", d, chars_off, chars)

    #
    # ACPI/EFI 镜像应同时具备 EXECUTABLE_IMAGE
    #
    if not (chars & IMAGE_FILE_EXECUTABLE_IMAGE):
        chars |= IMAGE_FILE_EXECUTABLE_IMAGE
        struct.pack_into("<H", d, chars_off, chars)

    #
    # 节表
    #
    opt_off = pe + 24
    num_sec = struct.unpack_from("<H", d, pe + 6)[0]
    opt_size = struct.unpack_from("<H", d, pe + 20)[0]
    sec_off = opt_off + opt_size
    sec_names = []
    for i in range(num_sec):
        base = sec_off + i * 40
        name = bytes(d[base:base + 8]).rstrip(b"\0").decode("ascii", "replace")
        sec_names.append(name)

    #
    # 导入表（数据目录第 1 项）
    #
    dirs = opt_off + (108 if struct.unpack_from("<H", d, opt_off)[0] == 0x20B else 92)
    import_rva, import_size = struct.unpack_from("<II", d, dirs + 8)

    open(path, "wb").write(bytes(d))

    print(f"--- {path}")
    print(f"    清掉 IMAGE_FILE_DLL : {'是（原为 0x2000）' if had_dll else '本来就干净'}")
    print(f"    Characteristics     : 0x{chars:04X}  (EXECUTABLE_IMAGE={bool(chars & IMAGE_FILE_EXECUTABLE_IMAGE)})")
    print(f"    节表               : {', '.join(sec_names)}")
    print(f"    导入表             : RVA=0x{import_rva:X} 大小={import_size}"
          f"  {'✅ 零导入（符合 UEFI 驱动惯例）' if import_size == 0 else '⚠️ 存在导入表'}")
    print()


if __name__ == "__main__":
    for f in (sys.argv[1:] or ["TpadAcpiProbe.efi", "TpadAcpiPatch.efi"]):
        try:
            fix(f)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {f}: {e}")
            sys.exit(1)
    print("后处理完成 ✅")
