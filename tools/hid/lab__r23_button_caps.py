#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r23_button_caps.py —— 列出本机 gxtp5100 四个集合的 Button caps 全表（只读）

动机：goodhaptic 的 Report 0x05 / 0x07 在本机 value caps 里没抓到，
      可能是以 **button/switch** 形式声明的（选择性上报 = Surface/Button Switch）。
      本工具补抓 HidP_GetButtonCaps（INPUT/FEATURE/OUTPUT 三型），闭合这个【未定】。

★ 纯只读：CreateFileW(access=0)，只调 HidP_GetButtonCaps。
"""
import ctypes
from ctypes import wintypes
import importlib.util
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('r22', os.path.join(_here, 'lab__r22_feature_caps.py'))
r22 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r22)

hd = ctypes.WinDLL('hid', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
hd.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hd.HidD_GetPreparsedData.restype = wintypes.BOOL
hd.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]


class HIDP_BC_RANGE(ctypes.Structure):
    _fields_ = [('UsageMin', wintypes.USHORT), ('UsageMax', wintypes.USHORT),
                ('StringMin', wintypes.USHORT), ('StringMax', wintypes.USHORT),
                ('DesignatorMin', wintypes.USHORT), ('DesignatorMax', wintypes.USHORT),
                ('DataIndexMin', wintypes.USHORT), ('DataIndexMax', wintypes.USHORT)]


class HIDP_BC_NOTRANGE(ctypes.Structure):
    _fields_ = [('Usage', wintypes.USHORT), ('Reserved1', wintypes.USHORT),
                ('StringIndex', wintypes.USHORT), ('Reserved2', wintypes.USHORT),
                ('DesignatorIndex', wintypes.USHORT), ('Reserved3', wintypes.USHORT),
                ('DataIndex', wintypes.USHORT), ('Reserved4', wintypes.USHORT)]


class HIDP_BC_UNION(ctypes.Union):
    _fields_ = [('Range', HIDP_BC_RANGE), ('NotRange', HIDP_BC_NOTRANGE)]


class HIDP_BUTTON_CAPS(ctypes.Structure):
    _fields_ = [('UsagePage', wintypes.USHORT), ('ReportID', ctypes.c_ubyte),
                ('IsAlias', ctypes.c_ubyte), ('BitField', wintypes.USHORT),
                ('LinkCollection', wintypes.USHORT), ('LinkUsage', wintypes.USHORT),
                ('LinkUsagePage', wintypes.USHORT), ('IsRange', ctypes.c_ubyte),
                ('IsStringRange', ctypes.c_ubyte), ('IsDesignatorRange', ctypes.c_ubyte),
                ('IsAbsolute', ctypes.c_ubyte), ('ReportCount', wintypes.USHORT),
                ('Reserved2', wintypes.USHORT * 4), ('u', HIDP_BC_UNION)]


hd.HidP_GetButtonCaps.argtypes = [ctypes.c_ubyte, ctypes.POINTER(HIDP_BUTTON_CAPS),
                                  ctypes.POINTER(wintypes.USHORT), ctypes.c_void_p]
hd.HidP_GetButtonCaps.restype = ctypes.c_long


def getbc(pp, rt):
    cnt = wintypes.USHORT(0)
    hd.HidP_GetButtonCaps(rt, None, ctypes.byref(cnt), pp)
    if cnt.value == 0:
        return [], 0x00110000
    arr = (HIDP_BUTTON_CAPS * cnt.value)()
    st = hd.HidP_GetButtonCaps(rt, arr, ctypes.byref(cnt), pp)
    out = []
    if (st & 0xFFFFFFFF) == 0x00110000:
        for i in range(cnt.value):
            c = arr[i]
            if c.IsRange:
                u = 'range 0x%04X..0x%04X' % (c.u.Range.UsageMin, c.u.Range.UsageMax)
            else:
                u = '0x%04X' % c.u.NotRange.Usage
            out.append((c.ReportID, c.UsagePage, c.LinkUsagePage, c.LinkUsage, u, c.ReportCount))
    return out, (st & 0xFFFFFFFF)


def main():
    paths = [p for p in r22.enum_paths() if 'gxtp5100' in p.lower()]
    print('=' * 104)
    print('### 本机 gxtp5100 Col01-04 · Button caps 全表（只读 access=0）')
    print('=' * 104)
    for p in sorted(paths, key=r22.col_tag):
        tag = r22.col_tag(p)
        h = k32.CreateFileW(p, 0, 3, None, 3, 0, None)
        if not h or h == ctypes.c_void_p(-1).value:
            print('\n%s 打开失败 err=%d' % (tag, ctypes.get_last_error()))
            continue
        pp = ctypes.c_void_p()
        if not hd.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            print('\n%s GetPreparsedData 失败' % tag)
            k32.CloseHandle(h)
            continue
        try:
            print('\n' + '-' * 104)
            print('集合 %s' % tag)
            for rt, nm in ((0, 'INPUT'), (2, 'FEATURE'), (1, 'OUTPUT')):
                b, st = getbc(pp, rt)
                print('    [%s] button caps = %d  status=%s' % (nm, len(b), hex(st)))
                for rid, up, lup, lu, u, rc in b:
                    print('        RID=0x%02X UP=0x%04X linkUP=0x%04X linkU=0x%04X usage=%s count=%d'
                          % (rid, up, lup, lu, u, rc))
        finally:
            hd.HidD_FreePreparsedData(pp)
            k32.CloseHandle(h)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
