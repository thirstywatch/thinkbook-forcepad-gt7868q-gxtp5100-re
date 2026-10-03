# gxhid.py —— Gx.cs 的 Python 等价实现（ctypes 直调 setupapi/hid/kernel32）
#
# 为什么存在：PowerShell 的 Add-Type 在受限环境里被禁止（运行时编译 .NET 代码），
#             而本项目的厂商内存通道只需要 CreateFileW + HidD_Set/GetInputReport。
#
# 协议（与 poc\Gx.cs 完全一致）：
#   16 位地址帧 / GTX8 家族
#     读: 0E 20 00 00 05 01 <addr16BE> <size16BE>
#     写: 0E 20 00 00 <len+5> 00 <addr16BE> <len16BE> <data...>
#   经 Col04 自身的 OUT 报表 (rid=0x0E, 65B) 发送；响应从 Col04 的 IN 报表读回
#   响应: 0E 20 <cont> <seq> <len> <data...>   cont=1 表示还有后续块
#
# 用法:
#   from gxhid import GxChannel
#   ch = GxChannel(); ch.open()
#   data, log = ch.read(0x4018, 4)

import ctypes
import ctypes.wintypes as wt
import time

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


def _guid_from_string(s):
    g = GUID()
    ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
    return g


def enum_paths(filter_sub=None, guid_str=HID_GUID):
    """枚举 HID 设备接口路径（可选子串过滤）"""
    out = []
    g = _guid_from_string(guid_str)
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
            cb = wt.DWORD(8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            ctypes.memmove(buf, ctypes.byref(cb), 4)
            if setupapi.SetupDiGetDeviceInterfaceDetailW(s, ctypes.byref(did), buf,
                                                         req.value, ctypes.byref(req), None):
                path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                if path and (filter_sub is None or filter_sub.lower() in path.lower()):
                    out.append(path)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(s)
    return out


def open_path(path, read=True, write=True):
    """按完整路径打开；返回 (handle, err)"""
    acc = 0
    if read:
        acc |= GENERIC_READ
    if write:
        acc |= GENERIC_WRITE
    h = k32.CreateFileW(path, acc, FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                        OPEN_EXISTING, 0, None)
    if not h or h == INVALID_HANDLE:
        return None, ctypes.get_last_error()
    return h, 0


class GxChannel:
    """厂商内存通道（Col04）。★ 只读用法：open() -> read()"""

    def __init__(self, col="col04", vendor="GXTP5100"):
        self.col = col
        self.vendor = vendor
        self.path = None
        self.handle = None

    def open(self):
        for p in enum_paths(self.vendor):
            if self.col.lower() in p.lower():
                self.path = p
                break
        if self.path is None:
            return False, "collection-not-found"
        self.handle, err = open_path(self.path)
        if not self.handle:
            return False, "open-failed err=%d" % err
        return True, self.path

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None

    def _send(self, pkt):
        b = (ctypes.c_ubyte * 65)()
        n = min(len(pkt), 65)
        for i in range(n):
            b[i] = pkt[i]
        b[0] = 0x0E
        ok = hid.HidD_SetOutputReport(self.handle, b, 65)
        return bool(ok), ctypes.get_last_error()

    def _recv(self):
        r = (ctypes.c_ubyte * 65)()
        r[0] = 0x0E
        ok = hid.HidD_GetInputReport(self.handle, r, 65)
        if not ok:
            return None, ctypes.get_last_error()
        return bytes(r), 0

    def read(self, addr, size, rounds=12, max_cont=1):
        """16 位地址读。返回 (data|None, log)
           max_cont: 允许的最大续块数（默认 1 = 只收第一块，与 Gx.Read 一致）
        """
        pkt = [0x0E, 0x20, 0x00, 0x00, 0x05, 0x01,
               (addr >> 8) & 0xFF, addr & 0xFF,
               (size >> 8) & 0xFF, size & 0xFF]
        ok, err = self._send(pkt)
        if not ok:
            return None, "send-fail err=%d" % err
        acc = bytearray()
        log = []
        for _ in range(rounds):
            time.sleep(0.06)
            r, err = self._recv()
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
        out = bytes(acc[:size]) if size else bytes(acc)
        return out, " ".join(log)

    def write(self, addr, data):
        """★ 危险：写设备内存/寄存器。调用方必须自行确认风险与回滚路径。
           16 位地址帧官方长度字段是 len+5（2026-09-29 修正，原先误写 +7 会被设备丢弃）
        """
        data = bytes(data)
        pkt = [0x0E, 0x20, 0x00, 0x00, (len(data) + 5) & 0xFF, 0x00,
               (addr >> 8) & 0xFF, addr & 0xFF,
               (len(data) >> 8) & 0xFF, len(data) & 0xFF] + list(data)
        ok, err = self._send(pkt)
        log = "write(0x%04X, %dB) len+5=%d -> %s err=%d" % (
            addr, len(data), (len(data) + 5) & 0xFF, ok, err)
        if ok:
            time.sleep(0.08)
            r, _ = self._recv()
            if r is not None:
                log += " | resp %02X %02X %02X %02X %02X" % (r[0], r[1], r[2], r[3], r[4])
        return ok, log


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


def health(ch, addr=0x4018):
    """健康门：0x4018 必须以 YELS 开头"""
    d, _ = ch.read(addr, 4)
    return bool(d) and asc(d).startswith("YELS"), d
