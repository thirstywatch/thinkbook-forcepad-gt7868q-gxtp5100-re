"""EC 间接读测试：out 0xD01/0xD02 设索引 → in 0xD03 取数据。
安全设计：单次运行、无循环轮询、前后保存/恢复 0xD01/0xD02、每步之间留间隔。"""
import ctypes, sys, time
from ctypes import wintypes
IOCTL_R8, IOCTL_W8 = 0x222810, 0x222814
class PortIo(ctypes.Structure):
    _fields_ = [("Port", ctypes.c_uint16), ("pad", ctypes.c_uint16), ("Value", ctypes.c_uint32)]
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
h = k32.CreateFileW("\\\\.\\RwDrv", 0xC0000000, 0, None, 3, 0x80, None)
if h in (-1, 0xFFFFFFFFFFFFFFFF):
    print("RwDrv 打开失败"); sys.exit(1)
def r8(p):
    q = PortIo(p, 0, 0); g = wintypes.DWORD(0)
    k32.DeviceIoControl(h, IOCTL_R8, ctypes.byref(q), ctypes.sizeof(q), ctypes.byref(q), ctypes.sizeof(q), ctypes.byref(g), None)
    return q.Value & 0xFF
def w8(p, v):
    q = PortIo(p, 0, v & 0xFF); g = wintypes.DWORD(0)
    return bool(k32.DeviceIoControl(h, IOCTL_W8, ctypes.byref(q), ctypes.sizeof(q), None, 0, ctypes.byref(g), None))

print("--- 稳定性基线：连读 3 次（间隔 0.3s） ---")
base = []
for k in range(3):
    cur = [r8(p) for p in (0xD00, 0xD01, 0xD02, 0xD03)]
    base.append(cur)
    print("  第%d次: %s" % (k+1, ["0x%02X" % v for v in cur]))
    if k < 2: time.sleep(0.3)
stable = all(b == base[0] for b in base)
print("  基线稳定: %s" % stable)
if not stable:
    print("  ⚠ 端口值在变动 —— 可能是活数据流，放弃写入测试"); sys.exit(0)

saved = (r8(0xD01), r8(0xD02))
print("\n--- 已保存 0xD01=0x%02X 0xD02=0x%02X ---" % saved)

REF = bytes.fromhex("000003130000000801039000003b5d00"
                    "500036272e25312ed0000000c0622002"
                    "00005003")   # 0xFE0B0400 前 24 字节
print("\n--- 间接读（索引 0x000..0x003 应与 0xFE0B0400 前 4 字节 %s 一致） ---"
      % " ".join("%02X" % c for c in REF[:4]))
results = {}
for addr in (0x000, 0x001, 0x002, 0x003, 0x010, 0x06C, 0x0FF, 0x100,
             0x2FF, 0x300, 0x400, 0x6FF, 0x700, 0x856):
    w8(0xD01, (addr >> 8) & 0xFF)
    w8(0xD02, addr & 0xFF)
    time.sleep(0.01)
    d = r8(0xD03)
    results[addr] = d
    note = ""
    if addr < len(REF):
        note = "  ≡ 窗口字节 0x%02X %s" % (REF[addr], "✔一致" if d == REF[addr] else "✘不一致")
    print("  索引 0x%04X (%4d) -> 0xD03 = 0x%02X%s" % (addr, addr, d, note))

w8(0xD01, saved[0]); w8(0xD02, saved[1])
time.sleep(0.1)
after = [r8(p) for p in (0xD00, 0xD01, 0xD02, 0xD03)]
print("\n--- 恢复后端口值: %s（应回到 %s） ---" % (["0x%02X" % v for v in after],
      ["0x%02X" % v for v in base[0]]))
print("  恢复成功: %s" % (after[1] == base[0][1] and after[2] == base[0][2]))
hit = sum(1 for a in range(4) if results.get(a) == REF[a])
print("\n结论：前 4 个索引匹配 %d/4 —— %s" % (hit, "端口路径 = 同一 EC RAM 空间的字节寻址 ✔" if hit == 4
      else "端口路径 与 内存窗口 不是同一寻址（见上表）"))
k32.CloseHandle(h)
