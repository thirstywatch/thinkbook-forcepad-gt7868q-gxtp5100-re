"""验证产物是不是合法的 UEFI PE32+ 驱动。
用法：python verify_pe.py TpadAcpiProbe.efi TpadAcpiPatch.efi
"""
import struct
import sys

SUBSYS = {
    0: "UNKNOWN", 2: "WINDOWS_GUI", 3: "WINDOWS_CUI",
    10: "EFI_APPLICATION", 11: "EFI_BOOT_SERVICE_DRIVER",
    12: "EFI_RUNTIME_DRIVER", 13: "EFI_ROM",
}
MACH = {0x8664: "x86-64", 0x14c: "i386", 0xaa64: "arm64"}


def check(path):
    d = open(path, "rb").read()
    if d[:2] != b"MZ":
        print(f"[FAIL] {path}: 没有 MZ 头")
        return False
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    if d[pe:pe + 4] != b"PE\0\0":
        print(f"[FAIL] {path}: PE 签名错")
        return False

    mach = struct.unpack_from("<H", d, pe + 4)[0]
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    chars = struct.unpack_from("<H", d, pe + 22)[0]
    magic = struct.unpack_from("<H", d, pe + 24)[0]
    ep = struct.unpack_from("<I", d, pe + 40)[0]
    imagebase = struct.unpack_from("<Q", d, pe + 24 + 24)[0]
    salign, falign = struct.unpack_from("<II", d, pe + 24 + 32)
    subsys = struct.unpack_from("<H", d, pe + 24 + 68)[0]
    dllchars = struct.unpack_from("<H", d, pe + 24 + 70)[0]

    ok = (mach == 0x8664) and (magic == 0x20B) and (subsys in (10, 11, 12, 13))

    print(f"--- {path}  ({len(d):,} 字节)")
    print(f"    Machine     0x{mach:04X}  {MACH.get(mach, '?')}")
    print(f"    Magic       0x{magic:04X}  ({'PE32+' if magic == 0x20B else 'PE32'})")
    print(f"    Subsystem   {subsys}  {SUBSYS.get(subsys, '?')}")
    print(f"    EntryPoint  RVA 0x{ep:X}   ImageBase 0x{imagebase:X}")
    print(f"    Align       section=0x{salign:X} file=0x{falign:X}  节数={nsec}")
    print(f"    FileChars   0x{chars:04X}   DllChars 0x{dllchars:04X}")
    print(f"    结论: {'✅ 合法的 UEFI PE32+ 驱动' if ok else '❌ 不符合预期'}")
    print()
    return ok


if __name__ == "__main__":
    files = sys.argv[1:] or ["TpadAcpiProbe.efi", "TpadAcpiPatch.efi"]
    all_ok = True
    for f in files:
        try:
            all_ok = check(f) and all_ok
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {f}: {e}")
            all_ok = False
    print("总体:", "全部通过 ✅" if all_ok else "有问题 ❌")
    sys.exit(0 if all_ok else 1)
