# -*- coding: utf-8 -*-
"""lab__r14_desc_probe.py — 读本机触控板 HID 报告描述符里的 X/Y LogicalMax（纯用户态，零风险）

为什么要自己写：
  `tools/hid/lab__RawRdesc.cs` 的注释里写着"纯用户态拿不到原始 rdesc" —— 这对【原始字节】成立，
  但我们并不需要原始字节：**LogicalMax 可以从解析后的 caps 里直接读**。
  `HidP_GetValueCaps(HidP_Input, ...)` 返回的 `HIDP_VALUE_CAPS` 数组里，
  每项都带 `UsagePage / Usage / LogicalMin / LogicalMax` ⇒ 取 (0x01, 0x30) 与 (0x01, 0x31) 即可。

用途：
  ★ 闭环本项目最大的一条悬案 —— "cfg 里 X/Y 点数 = 描述符 LogicalMax + 1"。
    步骤：把 cfg+0x10F 由 4150 改成 4151 → 重启（或重枚举）→ 再读本脚本
    ⇒ 若 X LogicalMax 变成 4150，则：① `+1` 规则被端到端证实；② cfg 写入的持久性被证实。

用法：python lab__r14_desc_probe.py
"""
import ctypes
from ctypes import wintypes

hid = ctypes.WinDLL('hid', use_last_error=True)
setupapi = ctypes.WinDLL('setupapi', use_last_error=True)

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
HidP_Input = 0
HidP_Output = 1
HidP_Feature = 2

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID = ctypes.c_void_p(-1).value


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.POINTER(ctypes.c_ulong))]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("ClassGuid", GUID),
                ("DevInst", wintypes.DWORD), ("Reserved", ctypes.POINTER(ctypes.c_ulong))]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", ctypes.c_ushort), ("UsagePage", ctypes.c_ushort),
                ("InputReportByteLength", ctypes.c_ushort), ("OutputReportByteLength", ctypes.c_ushort),
                ("FeatureReportByteLength", ctypes.c_ushort), ("Reserved", ctypes.c_ushort * 17),
                ("NumberLinkCollectionNodes", ctypes.c_ushort),
                ("NumberInputButtonCaps", ctypes.c_ushort), ("NumberInputValueCaps", ctypes.c_ushort),
                ("NumberInputDataIndices", ctypes.c_ushort),
                ("NumberOutputButtonCaps", ctypes.c_ushort), ("NumberOutputValueCaps", ctypes.c_ushort),
                ("NumberOutputDataIndices", ctypes.c_ushort),
                ("NumberFeatureButtonCaps", ctypes.c_ushort), ("NumberFeatureValueCaps", ctypes.c_ushort),
                ("NumberFeatureDataIndices", ctypes.c_ushort)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", ctypes.c_ushort), ("ReportID", ctypes.c_ubyte),
                ("IsAlias", ctypes.c_ubyte), ("BitField", ctypes.c_ushort),
                ("LinkCollection", ctypes.c_ushort), ("LinkUsage", ctypes.c_ushort),
                ("LinkUsagePage", ctypes.c_ushort),
                ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte),
                ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
                ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte),
                ("BitSize", ctypes.c_ushort), ("ReportCount", ctypes.c_ushort),
                ("Reserved2", ctypes.c_ushort * 5),
                ("UnitsExp", ctypes.c_ulong), ("Units", ctypes.c_ulong),
                ("LogicalMin", ctypes.c_long), ("LogicalMax", ctypes.c_long),
                ("PhysicalMin", ctypes.c_long), ("PhysicalMax", ctypes.c_long),
                ("_u", ctypes.c_ubyte * 8)]


hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS),
                                  ctypes.POINTER(ctypes.c_ushort), ctypes.c_void_p]
hid.HidP_GetUsageValue.argtypes = [ctypes.c_int, ctypes.c_ushort, ctypes.c_ushort,
                                   ctypes.c_ushort, ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [wintypes.HANDLE]


# ★ 64 位下必须显式声明原型，否则 HANDLE 会被截断成 int（第一次跑"扫描 0 个"就是这个原因）
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR,
                                         ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                 ctypes.POINTER(GUID), wintypes.DWORD,
                                                 ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p,
                                                      ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      ctypes.c_void_p, wintypes.DWORD,
                                                      ctypes.POINTER(wintypes.DWORD),
                                                      ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]


def enum_hid_paths():
    g = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(g))
    h = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None,
                                      DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    out = []
    i = 0
    while True:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(did)
        if not setupapi.SetupDiEnumDeviceInterfaces(h, None, ctypes.byref(g), i, ctypes.byref(did)):
            break
        need = wintypes.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(h, ctypes.byref(did), None, 0,
                                                  ctypes.byref(need), None)
        buf = ctypes.create_string_buffer(need.value)
        ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8
        if setupapi.SetupDiGetDeviceInterfaceDetailW(h, ctypes.byref(did), buf, need.value,
                                                     ctypes.byref(need), None):
            out.append(ctypes.wstring_at(ctypes.addressof(buf) + 4))
        i += 1
    setupapi.SetupDiDestroyDeviceInfoList(h)
    return out


def probe(path):
    h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID:
        return None
    try:
        pp = ctypes.c_void_p()
        if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            return None
        try:
            caps = HIDP_CAPS()
            if hid.HidP_GetCaps(pp, ctypes.byref(caps)) != 0x110000:
                return None
            res = {'usage_page': caps.UsagePage, 'usage': caps.Usage,
                   'in_len': caps.InputReportByteLength, 'out_len': caps.OutputReportByteLength,
                   'values': []}
            n = ctypes.c_ushort(caps.NumberInputValueCaps)
            if n.value:
                arr = (HIDP_VALUE_CAPS * n.value)()
                hid.HidP_GetValueCaps(HidP_Input, arr, ctypes.byref(n), pp)
                for k in range(n.value):
                    c = arr[k]
                    usages = []
                    if c.IsRange:
                        lo = ctypes.cast(ctypes.byref(c, HIDP_VALUE_CAPS._u.offset),
                                         ctypes.POINTER(ctypes.c_ushort))[0]
                        hi = ctypes.cast(ctypes.byref(c, HIDP_VALUE_CAPS._u.offset),
                                         ctypes.POINTER(ctypes.c_ushort))[1]
                        usages = list(range(lo, hi + 1))
                    else:
                        usages = [ctypes.cast(ctypes.byref(c, HIDP_VALUE_CAPS._u.offset),
                                              ctypes.POINTER(ctypes.c_ushort))[0]]
                    for u in usages:
                        res['values'].append((c.UsagePage, u, c.LogicalMin, c.LogicalMax,
                                              c.PhysicalMin, c.PhysicalMax, c.Units, c.UnitsExp,
                                              c.ReportID, c.BitSize))
            return res
        finally:
            hid.HidD_FreePreparsedData(pp)
    finally:
        k32.CloseHandle(h)


def main():
    paths = enum_hid_paths()
    hit = 0
    for p in paths:
        if 'VID_27C6' not in p.upper() and 'GXTP' not in p.upper():
            continue
        r = probe(p)
        if not r:
            continue
        hit += 1
        short = p.split('#')
        name = short[1] + '&' + short[2] if len(short) > 2 else p
        print('=' * 84)
        print('设备: %s' % name)
        print('  UsagePage=0x%04X Usage=0x%04X  in/out 报告长 = %d/%d'
              % (r['usage_page'], r['usage'], r['in_len'], r['out_len']))
        for (pg, u, lmin, lmax, pmin, pmax, units, uexp, rid, bits) in r['values']:
            tag = ''
            if pg == 0x01 and u == 0x30:
                tag = '   ★★★ X 坐标'
            elif pg == 0x01 and u == 0x31:
                tag = '   ★★★ Y 坐标'
            elif pg == 0x0D and u == 0x30:
                tag = '   ★ 压力(Tip Pressure)'
            elif pg == 0x0D and u == 0x51:
                tag = '   ★ Contact ID'
            print('   page=0x%02X usage=0x%02X Logical %d..%d  Physical %d..%d  units=%d exp=%d bits=%d rid=%d%s'
                  % (pg, u, lmin, lmax, pmin, pmax, units, uexp, bits, rid, tag))
    print('\n扫描 %d 个 HID 接口，匹配 Goodix %d 个' % (len(paths), hit))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
