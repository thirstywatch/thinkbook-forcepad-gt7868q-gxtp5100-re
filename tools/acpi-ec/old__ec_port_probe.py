"""EC 端口只读探测。默认只做 READ（IOCTL 0x222810），写操作需 --allow-write。"""
import ctypes, sys
from ctypes import wintypes

IOCTL_READ_IO8 = 0x222810
IOCTL_WRITE_IO8 = 0x222814

class PortIo(ctypes.Structure):
    _fields_ = [("Port", ctypes.c_uint16),
                ("pad", ctypes.c_uint16),
                ("Value", ctypes.c_uint32)]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

def open_drv():
    h = k32.CreateFileW("\\\\.\\RwDrv", 0xC0000000, 0, None, 3, 0x80, None)
    if h == -1 or h == 0xFFFFFFFFFFFFFFFF:
        return None, ctypes.get_last_error()
    return h, 0

def io_read(h, port):
    req = PortIo(port, 0, 0)
    got = wintypes.DWORD(0)
    ok = k32.DeviceIoControl(h, IOCTL_READ_IO8, ctypes.byref(req), ctypes.sizeof(req),
                             ctypes.byref(req), ctypes.sizeof(req), ctypes.byref(got), None)
    return (req.Value & 0xFF) if ok else None

def io_write(h, port, val):
    req = PortIo(port, 0, val & 0xFF)
    got = wintypes.DWORD(0)
    ok = k32.DeviceIoControl(h, IOCTL_WRITE_IO8, ctypes.byref(req), ctypes.sizeof(req),
                             None, 0, ctypes.byref(got), None)
    return bool(ok)

h, e = open_drv()
if h is None:
    print("RwDrv 打开失败 err=%d" % e); sys.exit(1)
print("RwDrv 已打开 ✔（只读模式）\n")

def scan(base, n, label):
    print("### %s  端口 0x%X..0x%X" % (label, base, base + n - 1))
    vals = []
    for p in range(base, base + n):
        v = io_read(h, p)
        vals.append(v)
        print("   0x%04X = %s" % (p, ("0x%02X" % v) if v is not None else "读失败"))
    print("   非 FF 的端口: %s\n" % [hex(base + i) for i, v in enumerate(vals) if v != 0xFF])
    return vals

scan(0xD00, 16, "候选 EC 间接访问块")
scan(0x60, 16, "传统 EC/KBC 端口")
scan(0x1800, 8, "ACPI PM 块（仅作对照）")

if "--allow-write" in sys.argv:
    print("=" * 70)
    print("试用 EC 间接读：out 0xD01/0xD02 设索引，读 0xD03")
    before = [io_read(h, p) for p in (0xD01, 0xD02, 0xD03)]
    print("  设索引前 0xD01/02/03 = %s" % ["0x%02X" % v if v is not None else "?" for v in before])
    for addr in (0x000, 0x001, 0x002, 0x100, 0x300, 0x400, 0x856):
        io_write(h, 0xD01, (addr >> 8) & 0xFF)
        io_write(h, 0xD02, addr & 0xFF)
        d = io_read(h, 0xD03)
        print("  索引 0x%04X -> 0xD03 = %s" % (addr, ("0x%02X" % d) if d is not None else "读失败"))
    for p, v in zip((0xD01, 0xD02), before[:2]):
        if v is not None: io_write(h, p, v)
    print("  已恢复 0xD01/0xD02 原值")
else:
    print("（未做任何写操作；如需测试间接读，加 --allow-write）")
k32.CloseHandle(h)
