# -*- coding: utf-8 -*-
"""hid_feature.py —— HID Feature Report 读写小工具（讲人话版）

为什么重写：
  项目历史上做 RID 9（Haptic Intensity）实验用的是 PowerShell + ColProbe.cs，
  那两个文件在工区整理时没进仓库（在旧 poc/ 目录）。本文件用纯 ctypes 重建，
  不依赖任何外部源码，方便以后任何人复现。

用法：
  python hid_feature.py list                      # 列出全部 HID 设备路径（含 Col）
  python hid_feature.py get <匹配串> <rid> <len>   # 读 feature
  python hid_feature.py set <匹配串> <rid> <bytes> # 写 feature（bytes 用空格分隔的 16 进制）

例：
  python hid_feature.py get gxtp5100&col02 9 1
  python hid_feature.py set gxtp5100&col02 9 0A
"""
import ctypes
import sys
from ctypes import wintypes

# ---------- 常量 ----------
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID = ctypes.c_void_p(-1).value

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
hid = ctypes.WinDLL('hid', use_last_error=True)
setupapi = ctypes.WinDLL('setupapi', use_last_error=True)

k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


GUID_S = "{4d1e55b2-f16f-11cf-88cb-001111000030}"

hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetHidGuid.restype = None
hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_SetFeature.restype = wintypes.BOOLEAN
hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_GetFeature.restype = wintypes.BOOLEAN


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("InterfaceClassGuid", ctypes.c_ubyte * 16),
                ("Flags", wintypes.DWORD),
                ("Reserved", ctypes.POINTER(ctypes.c_ulong))]


def enum_hid_paths():
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    h = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None,
                                      DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not h or h == INVALID:
        return []
    out = []
    i = 0
    while True:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(did)
        ok = setupapi.SetupDiEnumDeviceInterfaces(
            ctypes.c_void_p(h), None, ctypes.byref(guid), i, ctypes.byref(did))
        if not ok:
            break
        need = wintypes.DWORD(0)
        setupapi.SetupDiGetDeviceInterfaceDetailW(
            ctypes.c_void_p(h), ctypes.byref(did), None, 0, ctypes.byref(need), None)
        buf = ctypes.create_string_buffer(need.value)
        ctypes.memmove(buf, ctypes.byref(wintypes.DWORD(ctypes.sizeof(wintypes.DWORD) + 2)), 4)
        if setupapi.SetupDiGetDeviceInterfaceDetailW(
                ctypes.c_void_p(h), ctypes.byref(did), buf, need.value, None, None):
            out.append(ctypes.wstring_at(ctypes.addressof(buf) + 4))
        i += 1
    setupapi.SetupDiDestroyDeviceInfoList(ctypes.c_void_p(h))
    return out


COLPATH = {
    "col01": "\\\\?\\HID#GXTP5100&Col01#5&52a7aed&0&0000#" + GUID_S,
    "col02": "\\\\?\\HID#GXTP5100&Col02#5&52a7aed&0&0001#" + GUID_S,
    "col03": "\\\\?\\HID#GXTP5100&Col03#5&52a7aed&0&0002#" + GUID_S,
    "col04": "\\\\?\\HID#GXTP5100&Col04#5&52a7aed&0&0003#" + GUID_S,
}


def open_dev(path):
    """Col01/Col02 被 Windows 触摸板驱动独占，只能【只写】打开（历史 ColProbe 同款做法）。"""
    for rights, lbl in ((GENERIC_WRITE, "write-only"),
                        (GENERIC_READ | GENERIC_WRITE, "read+write"),
                        (GENERIC_READ, "read-only")):
        h = k32.CreateFileW(path, rights, FILE_SHARE_READ | FILE_SHARE_WRITE,
                            None, OPEN_EXISTING, 0, None)
        if h and h != INVALID:
            print("  (打开方式: %s)" % lbl)
            return h
    print("  打开失败 err=%d" % ctypes.get_last_error())
    return None


def find_path(pat):
    pat = pat.lower()
    if pat in COLPATH:
        return COLPATH[pat]
    for k, v in COLPATH.items():
        if pat in k:
            return v
    # 也允许直接传完整路径
    if pat.startswith("\\\\?\\"):
        return pat
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    mode = sys.argv[1]

    if mode == 'list':
        for k in sorted(COLPATH):
            h = open_dev(COLPATH[k])
            got = "OK" if h else "-"
            if h:
                k32.CloseHandle(h)
            print("  %s  %s" % (k, got))
        return 0

    if mode not in ('get', 'set'):
        print(__doc__)
        return 1

    path = find_path(sys.argv[2])
    if not path:
        print("找不到匹配 '%s' 的集合（可用: col01..col04 或完整路径）" % sys.argv[2])
        return 2
    print("设备: %s" % path)
    rid = int(sys.argv[3], 0)
    h = open_dev(path)
    if not h:
        return 3

    if mode == 'get':
        n = int(sys.argv[4], 0)
        buf = ctypes.create_string_buffer(n + 1)
        buf[0] = bytes([rid])
        ok = hid.HidD_GetFeature(h, ctypes.cast(buf, ctypes.c_void_p), n + 1)
        err = ctypes.get_last_error()
        if not ok:
            print("GetFeature FAILED err=%d" % err)
            k32.CloseHandle(h)
            return 4
        data = bytes(buf.raw[1:n + 1])
        print("  GetFeature(rid=%d, len=%d) -> %s" % (rid, n, " ".join("%02X" % b for b in data)))
    else:
        vals = [int(x, 16) for x in sys.argv[4].split()]
        buf = ctypes.create_string_buffer(len(vals) + 1)
        buf[0] = bytes([rid])
        ctypes.memmove(ctypes.addressof(buf) + 1, bytes(vals), len(vals))
        ok = hid.HidD_SetFeature(h, ctypes.cast(buf, ctypes.c_void_p), len(vals) + 1)
        err = ctypes.get_last_error()
        print("  SetFeature(rid=%d, data=%s) -> %s err=%d"
              % (rid, " ".join("%02X" % v for v in vals), "OK" if ok else "FAIL", err))

    k32.CloseHandle(h)
    return 0


if __name__ == '__main__':
    sys.exit(main())
