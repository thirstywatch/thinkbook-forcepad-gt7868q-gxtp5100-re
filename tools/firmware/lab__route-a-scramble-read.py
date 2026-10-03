# route-a-scramble-read.py —— 路线 A①：经厂商内存通道【只读】HW_REG_SCRAMBLE = 0x2218
#
# 与 poc\Gx.cs 完全等价的协议实现（用 ctypes 直调 setupapi/hid/kernel32，
# 避免 PowerShell Add-Type 的运行时编译）：
#   帧(16 位地址 / GTX8 家族)  读: 0E 20 00 00 05 01 <addr16BE> <size16BE>
#   经 Col04 自己的 OUT 报表 (rid=0x0E, 65B) 发送；响应从 Col04 的 IN 报表读回
#   响应: 0E 20 <cont> <seq> <len> <data...>   cont=1 表示还有后续块
#
# 依据（追加二十八 / 汇顶官方 gtx8_driver_linux/goodix_gtx8_update.c）：
#   #define HW_REG_SCRAMBLE 0x2218   // 官方在加载明文 ISP 前写 0x00 关掉加扰
#
# ★ 本脚本【全程零写入】。只回答一个问题：这个开关寄存器能不能读到。
#
# 用法: python route-a-scramble-read.py

import ctypes
import ctypes.wintypes as wt
import sys
import time
from datetime import datetime

setupapi = ctypes.WinDLL('setupapi', use_last_error=True)
hid = ctypes.WinDLL('hid', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)

HID_GUID = "{4d1e55b2-f16f-11cf-88cb-001111000030}"
DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3

INVALID_HANDLE = ctypes.c_void_p(-1).value


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD),
                ("Data2", wt.WORD),
                ("Data3", wt.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD),
                ("InterfaceClassGuid", GUID),
                ("Flags", wt.DWORD),
                ("Reserved", ctypes.c_void_p)]


def guid_from_string(s):
    g = GUID()
    ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
    return g


setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p,
                                         ctypes.c_void_p, wt.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                 ctypes.POINTER(GUID), wt.DWORD,
                                                 ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p,
                                                     ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                     ctypes.c_void_p, wt.DWORD,
                                                     ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                            wt.DWORD, wt.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]

hid.HidD_SetOutputReport.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
hid.HidD_GetInputReport.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]


def enum_paths(filter_sub):
    out = []
    g = guid_from_string(HID_GUID)
    s = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None,
                                      DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not s or s == INVALID_HANDLE:
        return out
    try:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        i = 0
        while setupapi.SetupDiEnumDeviceInterfaces(s, None, ctypes.byref(g), i,
                                                   ctypes.byref(did)):
            i += 1
            req = wt.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(s, ctypes.byref(did), None, 0,
                                                      ctypes.byref(req), None)
            if req.value == 0:
                continue
            buf = ctypes.create_string_buffer(req.value)
            ctypes.memset(buf, 0, req.value)
            # cbSize: 8 on x64, 6 on x86
            ctypes.memmove(buf, ctypes.byref(wt.DWORD(8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)), 4)
            if setupapi.SetupDiGetDeviceInterfaceDetailW(s, ctypes.byref(did), buf,
                                                         req.value, ctypes.byref(req), None):
                path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                if path and (filter_sub is None or filter_sub.lower() in path.lower()):
                    out.append(path)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(s)
    return out


def open_rw(path):
    h = k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID_HANDLE:
        return None, ctypes.get_last_error()
    return h, 0


def send(h, pkt):
    b = (ctypes.c_ubyte * 65)()
    n = min(len(pkt), 65)
    for i in range(n):
        b[i] = pkt[i]
    b[0] = 0x0E
    ok = hid.HidD_SetOutputReport(h, b, 65)
    return bool(ok), ctypes.get_last_error()


def recv(h):
    r = (ctypes.c_ubyte * 65)()
    r[0] = 0x0E
    ok = hid.HidD_GetInputReport(h, r, 65)
    if not ok:
        return None, ctypes.get_last_error()
    return bytes(r), 0


def read_mem(h, addr, size, rounds=12):
    """返回 (data, log) ；data 为 None 表示失败"""
    pkt = [0x0E, 0x20, 0x00, 0x00, 0x05, 0x01,
           (addr >> 8) & 0xFF, addr & 0xFF,
           (size >> 8) & 0xFF, size & 0xFF]
    ok, err = send(h, pkt)
    if not ok:
        return None, "send-fail err=%d" % err

    acc = bytearray()
    log = []
    for _ in range(rounds):
        time.sleep(0.06)
        r, err = recv(h)
        if r is None:
            log.append("recv-fail err=%d" % err)
            break
        cont, seq, ln = r[2], r[3], r[4]
        log.append("[c%d st%d len%d]" % (cont, seq, ln))
        ln = min(ln, 60)
        acc.extend(r[5:5 + ln])
        if cont == 0:
            break
    if not acc:
        return None, " ".join(log)
    return bytes(acc[:size]) if size else bytes(acc), " ".join(log)


def hx(d):
    if d is None:
        return "<null>"
    if len(d) == 0:
        return "<empty>"
    return " ".join("%02X" % b for b in d)


def asc(d):
    if not d:
        return ""
    return "".join(chr(b) if 32 <= b < 127 else "." for b in d)


LOG_PATH = r"<LAB>\touchpad-lab\poc\route-a-scramble-read-log.txt"
_lines = []


def W(s):
    print(s, flush=True)
    _lines.append(s)


W("=== 路线 A① 只读 0x2218 (HW_REG_SCRAMBLE) :: %s ===" % datetime.now().isoformat(timespec='seconds'))
W("全程只读，零写入。")

paths = enum_paths("GXTP5100")
W("GXTP5100 HID 接口数: %d" % len(paths))

target = None
for p in paths:
    if "col04" in p.lower():
        target = p
        break

if target is None:
    W("❌ 未找到 Col04 集合。现有集合：")
    for p in paths:
        W("   " + p)
    W("ABORT")
    sys.exit(3)

W("Col04 路径: " + target)
h, err = open_rw(target)
if not h:
    W("❌ Col04 读写句柄打不开 err=%d（可能需管理员 / 设备被占用）" % err)
    W("ABORT")
    sys.exit(1)
W("Col04 读写句柄 OK")

PACE = 0.6


def one(addr, size=4):
    d, lg = read_mem(h, addr, size)
    time.sleep(PACE)
    return d, lg


# ① 健康门
W("")
W("--- ① 健康门 ---")
d, lg = one(0x4018)
W("  0x4018 :: %s   [%s]   (%s)" % (hx(d), asc(d), lg))
if d is None or not asc(d).startswith("YELS"):
    W("  ❌ 健康门未通过 ⇒ ABORT，不做任何后续读")
    k32.CloseHandle(h)
    sys.exit(2)
W("  ✅ 健康门通过（芯片自报 YELSTO）")

d, lg = one(0x4014)
W("  0x4014 :: %s   [%s]   (版本寄存器)   (%s)" % (hx(d), asc(d), lg))

# ② 目标
W("")
W("--- ② ★ 目标：0x2218 (HW_REG_SCRAMBLE) ---")
d, lg = one(0x2218)
W("  0x2218 :: %s   [%s]   (%s)" % (hx(d), asc(d), lg))

# ③ 稳定性
W("")
W("--- ③ 稳定性复核（同地址再读 2 次）---")
for i in (1, 2):
    d, lg = one(0x2218)
    W("  #%d  0x2218 :: %s   (%s)" % (i, hx(d), lg))

# ④ 邻域
W("")
W("--- ④ 邻域括号读（判断真寄存器 vs 未映射）---")
for a in (0x2208, 0x2210, 0x2214, 0x221C, 0x2220):
    d, lg = one(a)
    W("  0x%04X :: %s   (%s)" % (a, hx(d), lg))

# ⑤ 对照
W("")
W("--- ⑤ 对照组（已知可读区，证明通道正常）---")
for a in (0x452C, 0x4160):
    d, lg = one(a)
    W("  0x%04X :: %s   [%s]   (%s)" % (a, hx(d), asc(d), lg))

# ⑥ 收尾健康
W("")
W("--- ⑥ 收尾健康检查 ---")
d, lg = one(0x4018)
W("  0x4018 :: %s   [%s]" % (hx(d), asc(d)))
if asc(d).startswith("YELS"):
    W("  ✅ 设备健康，与开读前一致")
else:
    W("  ⚠ 健康状态与开读前不一致（只读操作理论上不应改变任何状态）")

k32.CloseHandle(h)
W("")
W("完成（全程只读，零写入）。")

with open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(_lines) + "\n")
print("\n[log] " + LOG_PATH)
