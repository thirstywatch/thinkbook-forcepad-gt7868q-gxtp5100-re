"""只读探测 EC 内存窗口 0xFE0B0000（含 ACPI ECMM 之前的 1 KB）。
仅使用 READ IOCTL (0x222808)，绝不写。"""
import ctypes, sys
from ctypes import wintypes

IOCTL_READ_PHYS = 0x222808
class PhysRw(ctypes.Structure):
    _fields_ = [("physicalAddress", ctypes.c_ulonglong),
                ("size", ctypes.c_uint32),
                ("access", ctypes.c_uint32),
                ("buffer", ctypes.c_ulonglong)]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
GENERIC_RW = 0xC0000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

def open_drv():
    h = k32.CreateFileW("\\\\.\\RwDrv", GENERIC_RW, 0, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if h == -1 or h == 0xFFFFFFFFFFFFFFFF:
        return None, ctypes.get_last_error()
    return h, 0

def read_phys(h, addr, n):
    buf = (ctypes.c_ubyte * n)()
    req = PhysRw(addr, n, 0, ctypes.cast(buf, ctypes.c_void_p).value)
    got = wintypes.DWORD(0)
    ok = k32.DeviceIoControl(h, IOCTL_READ_PHYS, ctypes.byref(req), ctypes.sizeof(req),
                             None, 0, ctypes.byref(got), None)
    if not ok:
        return None, ctypes.get_last_error()
    return bytes(buf), 0

h, e = open_drv()
if h is None:
    print("无法打开 \\\\.\\RwDrv  err=%d  (2=驱动未加载, 5=权限不足)" % e); sys.exit(1)
print("RwDrv 已打开 ✔\n")

REGIONS = [(0xFE0B0000, 0x400, "EC 窗口基址前 1 KB (无 ACPI 映射)"),
           (0xFE0B0400, 0x300, "ECMM 起始 768 B (已知可读)"),
           (0xFE0B0700, 0x100, "ECMM 0x300..0x400 (已知读到 FF)")]
for addr, n, label in REGIONS:
    data, e = read_phys(h, addr, n)
    print("=" * 74)
    if data is None:
        print("### 0x%08X 读取失败 err=%d" % (addr, e)); continue
    nonff = sum(1 for c in data if c != 0xFF)
    print("### 0x%08X  %s   len=0x%X   非FF字节=%d (%.0f%%)" % (addr, label, n, nonff, 100*nonff/n))
    for i in range(0, min(n, 0x180), 16):
        b = data[i:i+16]
        print("  +%04X  %s  |%s|" % (i, " ".join("%02X" % c for c in b),
              "".join(chr(c) if 32 <= c < 127 else "." for c in b)))
    # 签名探测：驱动用 0x5A / 0xA5 判定内存窗口可用
    for sig in (b"\x5a\xa5", b"\xa5\x5a", b"\x5a", b"\xa5"):
        c = data.count(sig[0]) if len(sig) == 1 else data.count(sig)
        if c: print("   签名 %s 出现 %d 次" % (sig.hex(" "), c))
k32.CloseHandle(h)
