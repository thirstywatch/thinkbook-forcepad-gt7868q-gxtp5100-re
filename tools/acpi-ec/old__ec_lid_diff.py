"""EC 窗口快照与差分工具。
  python ec_lid_diff.py snap <名字>    # 抓 768 字节快照
  python ec_lid_diff.py diff <A> <B>   # 差分两个快照，列出翻转的位
只读物理内存 0xFE0B0400，无任何写操作。"""
import ctypes, sys, os, json
from ctypes import wintypes
IOCTL_READ_PHYS = 0x222808
BASE, SIZE = 0xFE0B0400, 0x300
SNAPDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ec-lid-snaps")

class PhysRw(ctypes.Structure):
    _fields_ = [("physicalAddress", ctypes.c_ulonglong), ("size", ctypes.c_uint32),
                ("access", ctypes.c_uint32), ("buffer", ctypes.c_ulonglong)]
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
h = k32.CreateFileW("\\\\.\\RwDrv", 0xC0000000, 0, None, 3, 0x80, None)
if h in (-1, 0xFFFFFFFFFFFFFFFF):
    print("RwDrv 打开失败"); sys.exit(1)

def snap_read(n=SIZE):
    buf = (ctypes.c_ubyte * n)()
    req = PhysRw(BASE, n, 0, ctypes.cast(buf, ctypes.c_void_p).value)
    got = wintypes.DWORD(0)
    ok = k32.DeviceIoControl(h, IOCTL_READ_PHYS, ctypes.byref(req), ctypes.sizeof(req),
                             None, 0, ctypes.byref(got), None)
    return bytes(buf) if ok else None

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "snap":
    name = sys.argv[2] if len(sys.argv) > 2 else "snap"
    os.makedirs(SNAPDIR, exist_ok=True)
    d = snap_read()
    if d is None: print("读取失败"); sys.exit(1)
    p = os.path.join(SNAPDIR, name + ".bin"); open(p, "wb").write(d)
    print("已写入 %s (%d 字节)" % (p, len(d)))
    print("前 32 字节: %s" % " ".join("%02X" % c for c in d[:32]))
elif cmd == "diff":
    A = open(os.path.join(SNAPDIR, sys.argv[2] + ".bin"), "rb").read()
    B = open(os.path.join(SNAPDIR, sys.argv[3] + ".bin"), "rb").read()
    n = min(len(A), len(B))
    bytechg = [(i, A[i], B[i]) for i in range(n) if A[i] != B[i]]
    print("=== 变化的字节: %d 个 ===" % len(bytechg))
    for i, a, b in bytechg[:40]:
        print("  +0x%03X (位 %d.%d~%d)  %02X -> %02X   XOR=%02X  位翻转: %s"
              % (i, i, 0, 7, a, b, a ^ b,
                 [j for j in range(8) if (a ^ b) >> j & 1]))
    if len(bytechg) > 40: print("  ... 还有 %d 个" % (len(bytechg) - 40))
    print("\n=== 翻转的单个位（最可能是 LIDF 这类布尔标志） ===")
    singles = [(i, j, (A[i] >> j) & 1, (B[i] >> j) & 1) for i, a, b in bytechg
               for j in range(8) if bin(a ^ b).count("1") == 1]
    for i, j, va, vb in singles:
        print("  位 %d.%d: %d -> %d" % (i, j, va, vb))
    if not singles: print("  （无单比特翻转）")
else:
    print(__doc__)
k32.CloseHandle(h)
