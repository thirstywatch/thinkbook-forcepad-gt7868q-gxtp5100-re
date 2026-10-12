#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r15_newton_verbatim.py —— 逐字照搬 edimetia3d/GoodixNewtonTouchpad 的 set/status 行为

【本文件的原则：不做任何"改进"，不绕过任何判据，不猜测、不替换任何常量。】
来源（全部照搬）：
    edimetia3d/GoodixNewtonTouchpad
      Program.cs : ParseLevel / SetLevel（mutex + 每次重新枚举 + SelectTarget + Write）
      Hid.cs     : Enumerate / ReadDescriptor / IsTarget / SelectTarget / Report / Write

照搬后的必然结果（本工具的设计意图）：
    IsTarget 要求 VID/PID 27C6/0F9A、UP/Usage FF00/0001、In/Out 9/9、Feature 0。
    本机 Col04 是 27C6/01E9、FF00/0001、65/65/0。
    ⇒ 匹配数 = 0
    ⇒ 照搬 SelectTarget() 必抛 InvalidOperationException
    ⇒ **不会发出任何数据包**

★ 这是 Newton 作者自己写的保护逻辑：不匹配就拒绝写。
  照搬他 = 拒绝写。这正是"他怎么做你就怎么做"的结果。

用法：
    python lab__r15_newton_verbatim.py status
    python lab__r15_newton_verbatim.py set low
    python lab__r15_newton_verbatim.py set medium
    python lab__r15_newton_verbatim.py set high
"""

import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

# ============================================================================
# 以下为 Hid.cs 的逐条照搬
# ============================================================================

hid = ctypes.WinDLL("hid.dll")
setupapi = ctypes.WinDLL("setupapi.dll")
kernel32 = ctypes.WinDLL("kernel32.dll")

# Hid.cs: 常量
PRESENT_DEVICE_INTERFACES = 0x12   # DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
GENERIC_WRITE_FLAG = 0x40000000
SHARE_READ_WRITE = 3
OPEN_EXISTING = 3
OVERLAPPED_IO = 0x40000000
NO_MORE_ITEMS = 259
INSUFFICIENT_BUFFER = 122
IO_PENDING = 997
HID_SUCCESS = 0x110000
REPORT_LENGTH = 9
WRITE_TIMEOUT_MS = 2000

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
WAIT_OBJECT_0 = 0


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT),
                ("ProductID", wintypes.USHORT), ("VersionNumber", wintypes.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    """Hid.cs 的 caps 结构（Reserved 17 个 ushort 后接计数字段）"""
    _fields_ = [
        ("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.POINTER(wintypes.ULONG))]


hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOL
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = wintypes.BOOL

setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR,
                                         ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
    wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.c_void_p]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                               ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
kernel32.WriteFile.restype = wintypes.BOOL
kernel32.GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                         ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
kernel32.GetOverlappedResult.restype = wintypes.BOOL
kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.CancelIoEx.restype = wintypes.BOOL
kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL,
                                  wintypes.LPCWSTR]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def _last_error():
    return ctypes.get_last_error() or 0


# ---- Hid.cs: Enumerate() ----
def enumerate_devices():
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    info = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None,
                                         PRESENT_DEVICE_INTERFACES)
    if not info or info == INVALID_HANDLE_VALUE:
        raise OSError("SetupDiGetClassDevs failed")
    devices = []
    try:
        index = 0
        while True:
            did = SP_DEVICE_INTERFACE_DATA()
            did.cbSize = ctypes.sizeof(did)
            if not setupapi.SetupDiEnumDeviceInterfaces(info, None, ctypes.byref(guid),
                                                       index, ctypes.byref(did)):
                # Hid.cs: error == NoMoreItems -> break
                break
            index += 1
            needed = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(did), None, 0,
                                                     ctypes.byref(needed), None)
            if needed.value < 8:
                continue
            buf = ctypes.create_string_buffer(needed.value)
            # Hid.cs: cbSize = 8 on x64, 6 on x86; path offset always 4
            cb = ctypes.c_uint32(8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            ctypes.memmove(buf, ctypes.byref(cb), 4)
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(did), buf,
                                                           needed.value,
                                                           ctypes.byref(needed), None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            d = read_descriptor(path)
            if d is not None:
                devices.append(d)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info)
    return devices


# ---- Hid.cs: ReadDescriptor() ----
def read_descriptor(path):
    # access=0：只查询属性，不申请读/写权限
    h = kernel32.CreateFileW(path, 0, SHARE_READ_WRITE, None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID_HANDLE_VALUE:
        return None
    try:
        attrs = HIDD_ATTRIBUTES()
        attrs.Size = ctypes.sizeof(attrs)
        if not hid.HidD_GetAttributes(h, ctypes.byref(attrs)):
            return None
        pp = ctypes.c_void_p()
        if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            return None
        try:
            caps = HIDP_CAPS()
            if hid.HidP_GetCaps(pp, ctypes.byref(caps)) != HID_SUCCESS:
                return None
            return {
                "Path": path,
                "Vid": attrs.VendorID,
                "Pid": attrs.ProductID,
                "UsagePage": caps.UsagePage,
                "Usage": caps.Usage,
                "InputLength": caps.InputReportByteLength,
                "OutputLength": caps.OutputReportByteLength,
                "FeatureLength": caps.FeatureReportByteLength,
            }
        finally:
            hid.HidD_FreePreparsedData(pp)
    finally:
        kernel32.CloseHandle(h)


# ---- Hid.cs: IsTarget() ---- 一字不改
def is_target(d):
    return (d["Vid"] == 0x27C6 and d["Pid"] == 0x0F9A
            and d["UsagePage"] == 0xFF00 and d["Usage"] == 1
            and d["InputLength"] == REPORT_LENGTH
            and d["OutputLength"] == REPORT_LENGTH
            and d["FeatureLength"] == 0)


# ---- Hid.cs: SelectTarget() ---- 一字不改（含其抛异常行为）
def select_target(devices):
    matches = [d for d in devices if is_target(d)]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one compatible Goodix HID collection; found %d" % len(matches))
    return matches[0]


# ---- Hid.cs: Report() ---- 一字不改
def report(level):
    if level < 0 or level > 2:
        raise ValueError("level")
    # Verified protocol: report ID 0E, operation 02, level 0/1/2, six zero bytes.
    return bytes([0x0E, 0x02, level, 0, 0, 0, 0, 0, 0])


# ---- Hid.cs: Write() ---- 照搬（overlapped + 事件 + 超时取消）
def write_report(device, level):
    if not is_target(device):
        raise RuntimeError("Unverified device descriptor.")
    rep = report(level)
    h = kernel32.CreateFileW(device["Path"], GENERIC_WRITE_FLAG, SHARE_READ_WRITE,
                             None, OPEN_EXISTING, OVERLAPPED_IO, None)
    if not h or h == INVALID_HANDLE_VALUE:
        raise OSError(_last_error(), "Cannot open HID output collection.")
    completed = kernel32.CreateEventW(None, True, False, None)
    if not completed:
        kernel32.CloseHandle(h)
        raise OSError("CreateEvent failed")
    buf = ctypes.create_string_buffer(rep, len(rep))
    try:
        written = wintypes.DWORD(0)
        # OVERLAPPED 结构：本工具用固定 8 字节对齐布局（x64）
        class OVERLAPPED(ctypes.Structure):
            _fields_ = [("Internal", ctypes.c_void_p),
                        ("InternalHigh", ctypes.c_void_p),
                        ("Offset", wintypes.DWORD),
                        ("OffsetHigh", wintypes.DWORD),
                        ("hEvent", wintypes.HANDLE)]
        ov = OVERLAPPED()
        ov.hEvent = completed
        synchronous = kernel32.WriteFile(h, buf, len(rep), ctypes.byref(written),
                                         ctypes.byref(ov))
        if not synchronous:
            err = _last_error()
            if err != IO_PENDING:
                raise OSError(err, "HID WriteFile failed.")
            wait = kernel32.WaitForSingleObject(completed, WRITE_TIMEOUT_MS)
            if wait != WAIT_OBJECT_0:
                kernel32.CancelIoEx(h, ctypes.byref(ov))
                kernel32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(written), True)
                raise TimeoutError("HID write wait failed or timed out; cancellation requested.")
        if not kernel32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(written), True):
            raise OSError(_last_error(), "HID write completion failed.")
        if written.value != len(rep):
            raise IOError("Incomplete HID report: %d" % written.value)
    finally:
        kernel32.CloseHandle(completed)
        kernel32.CloseHandle(h)
    return rep


# ============================================================================
# 以下为 Program.cs 的逐条照搬
# ============================================================================

def parse_level(text):
    t = text.lower()
    if t in ("low", "0", "低"):
        return 0
    if t in ("medium", "1", "中"):
        return 1
    if t in ("high", "2", "高"):
        return 2
    raise ValueError("Use low, medium or high (0, 1 or 2).")


def _user_mutex_name():
    """Program.cs 用 SID 构造 mutex 名；Python 版等价实现（按用户隔离 + 串行化）。"""
    return "Local\\GoodixNewtonTouchpad.Write." + (os.environ.get("USERNAME") or "user")


def set_level(level):
    lock_path = os.path.join(os.environ.get("TEMP", "."), "gnt_write.lock")
    lock_fd = None
    acquired = False
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
                acquired = True
                break
            except OSError:
                time.sleep(0.05)
        if not acquired:
            raise TimeoutError("Another write is in progress.")

        # Enumerate on every invocation instead of reusing a stored device path.
        device = select_target(enumerate_devices())
        rep = write_report(device, level)
        print(json.dumps({
            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": level,
            "report": "-".join("%02X" % b for b in rep),
            "transport": "WriteFile completed",
            "hardwareState": "unverified-no-readback",
        }, ensure_ascii=False))
    finally:
        if lock_fd is not None:
            try:
                if acquired and os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            os.close(lock_fd)


def print_status():
    devices = [d for d in enumerate_devices() if is_target(d)]
    print(json.dumps({
        "targetCount": len(devices),
        "devices": devices,
        "hardwareState": "unverified-no-readback",
    }, ensure_ascii=False, indent=2))


def main():
    args = sys.argv[1:]
    try:
        if len(args) == 1 and args[0] == "status":
            print_status()
        elif len(args) == 2 and args[0] == "set":
            set_level(parse_level(args[1]))
        else:
            sys.stderr.write("GoodixNewtonTouchpad status | set low|medium|high\n")
            return 2
        return 0
    except Exception as e:
        sys.stderr.write(type(e).__name__ + ": " + str(e) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
