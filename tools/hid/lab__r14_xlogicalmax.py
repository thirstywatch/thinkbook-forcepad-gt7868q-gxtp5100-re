# -*- coding: utf-8 -*-
"""lab__r14_xlogicalmax.py — 读触控板 HID 描述符里的 X/Y LogicalMin/Max（纯 Python，只读）

用途：为"cfg +0x10F 写入是否被固件消费"提供【客观、可读回】的判据。
      出厂：cfg +0x10F = 4150（X 点数）⇒ 描述符里 X 的 LogicalMax 应为 4149 = 点数 − 1。
      把 +0x10F 改成 4151、重新枚举后若 LogicalMax 变 4150 ⇒ 写入被消费，**闭环成立**。

★ 全程只读：
  - CreateFileW(access=0) —— 只查询属性，不请求读写，故不会与驱动冲突（避开 err=32）
  - 仅调用 HidD_GetPreparsedData + HidP_GetValueCaps
  - **不发送任何 Output Report / SetFeature**

用法：
  python lab__r14_xlogicalmax.py            # 打印全部 Col 的关键字段
  python lab__r14_xlogicalmax.py --json     # 机器可读输出（供自动比对）
"""
import ctypes
import json
import sys
from ctypes import wintypes

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID = ctypes.c_void_p(-1).value
HIDP_STATUS_SUCCESS = 0x00110000
HIDP_INPUT = 0

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
hd = ctypes.WinDLL('hid', use_last_error=True)
setup = ctypes.WinDLL('setupapi', use_last_error=True)

k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [wintypes.HANDLE]

hd.HidD_GetHidGuid.argtypes = [ctypes.c_void_p]
hd.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hd.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]


class GUID(ctypes.Structure):
    _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                ('Data3', wintypes.WORD), ('Data4', ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('InterfaceClassGuid', GUID),
                ('Flags', wintypes.DWORD), ('Reserved', ctypes.c_void_p)]


setup.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setup.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p,
                                       ctypes.c_void_p, wintypes.DWORD]
setup.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                              ctypes.POINTER(GUID), wintypes.DWORD,
                                              ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p,
                                                   ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                   ctypes.c_void_p, wintypes.DWORD,
                                                   ctypes.POINTER(wintypes.DWORD),
                                                   ctypes.c_void_p]
setup.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]


class HIDP_RANGE(ctypes.Structure):
    _fields_ = [('UsageMin', wintypes.USHORT), ('UsageMax', wintypes.USHORT),
                ('StringMin', wintypes.USHORT), ('StringMax', wintypes.USHORT),
                ('DesignatorMin', wintypes.USHORT), ('DesignatorMax', wintypes.USHORT),
                ('DataIndexMin', wintypes.USHORT), ('DataIndexMax', wintypes.USHORT)]


class HIDP_NOTRANGE(ctypes.Structure):
    _fields_ = [('Usage', wintypes.USHORT), ('Reserved1', wintypes.USHORT),
                ('StringIndex', wintypes.USHORT), ('Reserved2', wintypes.USHORT),
                ('DesignatorIndex', wintypes.USHORT), ('Reserved3', wintypes.USHORT),
                ('DataIndex', wintypes.USHORT), ('Reserved4', wintypes.USHORT)]


class HIDP_UNION(ctypes.Union):
    _fields_ = [('Range', HIDP_RANGE), ('NotRange', HIDP_NOTRANGE)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ('UsagePage', wintypes.USHORT), ('ReportID', ctypes.c_ubyte),
        ('IsAlias', ctypes.c_ubyte), ('BitField', wintypes.USHORT),
        ('LinkCollection', wintypes.USHORT), ('LinkUsage', wintypes.USHORT),
        ('LinkUsagePage', wintypes.USHORT), ('IsRange', ctypes.c_ubyte),
        ('IsStringRange', ctypes.c_ubyte), ('IsDesignatorRange', ctypes.c_ubyte),
        ('IsAbsolute', ctypes.c_ubyte), ('HasNull', ctypes.c_ubyte),
        ('Reserved', ctypes.c_ubyte), ('BitSize', wintypes.USHORT),
        ('ReportCount', wintypes.USHORT), ('Reserved2', wintypes.USHORT * 5),
        ('UnitsExp', wintypes.ULONG), ('Units', wintypes.ULONG),
        ('LogicalMin', ctypes.c_long), ('LogicalMax', ctypes.c_long),
        ('PhysicalMin', ctypes.c_long), ('PhysicalMax', ctypes.c_long),
        ('u', HIDP_UNION),
    ]


hd.HidP_GetValueCaps.argtypes = [ctypes.c_ubyte, ctypes.POINTER(HIDP_VALUE_CAPS),
                                 ctypes.POINTER(wintypes.USHORT), ctypes.c_void_p]


def enum_paths():
    g = GUID()
    hd.HidD_GetHidGuid(ctypes.byref(g))
    s = setup.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)
    if s in (None, 0) or s == ctypes.c_void_p(-1).value:
        return []
    out = []
    try:
        i = 0
        while True:
            d = SP_DEVICE_INTERFACE_DATA()
            d.cbSize = ctypes.sizeof(d)
            if not setup.SetupDiEnumDeviceInterfaces(s, None, ctypes.byref(g), i,
                                                     ctypes.byref(d)):
                break
            need = wintypes.DWORD(0)
            setup.SetupDiGetDeviceInterfaceDetailW(s, ctypes.byref(d), None, 0,
                                                   ctypes.byref(need), None)
            if need.value:
                buf = ctypes.create_string_buffer(need.value)
                ctypes.memmove(buf, ctypes.byref(
                    wintypes.DWORD(8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)), 4)
                if setup.SetupDiGetDeviceInterfaceDetailW(s, ctypes.byref(d), buf,
                                                          need, ctypes.byref(need), None):
                    p = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                    if 'gxtp5100' in p.lower() or '27c6' in p.lower():
                        out.append(p)
            i += 1
    finally:
        setup.SetupDiDestroyDeviceInfoList(s)
    return out


def read_col(path):
    # access=0：只查询属性，不请求读写 ⇒ 不会 err=32
    h = k32.CreateFileW(path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID:
        return None, "CreateFile err=%d" % ctypes.get_last_error()
    try:
        pp = ctypes.c_void_p()
        if not hd.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            return None, "GetPreparsedData err=%d" % ctypes.get_last_error()
        try:
            cnt = wintypes.USHORT(0)
            hd.HidP_GetValueCaps(HIDP_INPUT, None, ctypes.byref(cnt), pp)
            if cnt.value == 0:
                return [], None
            buf = (HIDP_VALUE_CAPS * cnt.value)()
            st = hd.HidP_GetValueCaps(HIDP_INPUT, buf, ctypes.byref(cnt), pp)
            if (st & 0xFFFFFFFF) != HIDP_STATUS_SUCCESS:
                return None, "GetValueCaps status=0x%08X" % (st & 0xFFFFFFFF)
            res = []
            for i in range(cnt.value):
                c = buf[i]
                umin, umax = ((c.u.Range.UsageMin, c.u.Range.UsageMax) if c.IsRange
                              else (c.u.NotRange.Usage, c.u.NotRange.Usage))
                res.append({'RID': c.ReportID, 'UP': c.UsagePage, 'UMin': umin,
                            'UMax': umax, 'LogMin': c.LogicalMin, 'LogMax': c.LogicalMax,
                            'PhysMin': c.PhysicalMin, 'PhysMax': c.PhysicalMax,
                            'BitSize': c.BitSize})
            return res, None
        finally:
            hd.HidD_FreePreparsedData(pp)
    finally:
        k32.CloseHandle(h)


def col_tag(path):
    low = path.lower()
    for c in ('col01', 'col02', 'col03', 'col04'):
        if c in low:
            return c.upper()
    return '?'


def main():
    as_json = '--json' in sys.argv
    paths = enum_paths()
    report = {}
    for p in sorted(paths, key=col_tag):
        tag = col_tag(p)
        caps, err = read_col(p)
        if err:
            report[tag] = {'error': err}
            continue
        report[tag] = caps

    if as_json:
        print(json.dumps(report, indent=2))
        return 0

    print("=" * 88)
    print("### 触控板 HID 描述符 · Input value caps（只读，access=0，不发任何报文）")
    print("=" * 88)
    for tag in sorted(report):
        caps = report[tag]
        print("\n--- %s ---" % tag)
        if isinstance(caps, dict):
            print("    <失败: %s>" % caps.get('error'))
            continue
        for c in caps:
            mark = ""
            if c['UP'] == 0x01 and c['UMin'] <= 0x30 <= c['UMax']:
                mark = "   ★★★★★ X"
            elif c['UP'] == 0x01 and c['UMin'] <= 0x31 <= c['UMax']:
                mark = "   ★★★★★ Y"
            elif c['UP'] == 0x0D and c['UMin'] <= 0x30 <= c['UMax']:
                mark = "        TipPressure"
            print("    RID=%2d UP=0x%04X U=0x%04X..0x%04X  logi[%d..%d]  phys[%d..%d]  bits=%d%s"
                  % (c['RID'], c['UP'], c['UMin'], c['UMax'], c['LogMin'], c['LogMax'],
                     c['PhysMin'], c['PhysMax'], c['BitSize'], mark))
    print()
    print("判读：出厂应见 X logi[0..4149]（+0x10F 的 4150 − 1）、Y logi[0..2147]（2148 − 1）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
