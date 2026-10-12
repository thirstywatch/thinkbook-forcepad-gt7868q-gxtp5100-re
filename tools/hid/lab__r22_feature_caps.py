#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab__r22_feature_caps.py —— 列出本机所有 HID 集合的【Feature + Output】value caps 全表

动机（2026-10-08）：
  检索 GitHub 命中 nwkyz/goodhaptic（Linux，GXTP5100，ThinkBook 16 G8+ IPD），
  它用 **HID Feature Report** 控制触觉，并列出其设备的 vendor report 全表：

     0x02 Feature 2B   设备能力（Digitizers 0x0D: 0x55 Contact Max + 0x59 Pad Type）
     0x08 Feature 2B   点击力度阈值（Digitizers 0x0D: Usage 0xB0）1-3 档
     0x09 Feature 2B   ★ Haptics (0x0E) Intensity (0x23)，0-100
     0x03 Feature 2B   Input Mode（Digitizers 0x0D: 0x52）
     0x05 Feature 3B   Surface/Button 选择上报
     0x07 Feature 3B   Latency Mode（0x0D: 0x60）
     0x06 Feature 256B Vendor init blob（FF00: 0xC5）
     0x0B Feature 66B  Vendor status（FF00: 0xC7）
     0x0C Feature 736B Vendor config（FF00: 0xC6）
     0x0D Feature 4B   Vendor 固件命令（FF00: 0xC4）
     0x0E In/Out 64B   Vendor 双向通道  ← 本机 Col04 正是 Output RID 14 = 0x0E！

本工具：把本机所有集合的 Feature/Output value caps 逐条列出，
        与 goodhaptic 的表逐项对照，看本机有哪些、缺哪些。

★ 纯只读：CreateFileW(access=0)，只调 HidP_GetValueCaps，不发任何 report。

修订（r22b）：
  r22 首版 HIDP_NOTRANGE 只写了 3 个字段，导致 sizeof(HIDP_VALUE_CAPS) 偏小、
  数组步长错位 ⇒ 全表读空。现改为与 lab__r14 一致的【完整 8×USHORT】布局。
"""
import ctypes
import json
import sys
from ctypes import wintypes

INVALID = ctypes.c_void_p(-1).value
HIDP_STATUS_SUCCESS = 0x00000000 if False else 0x00110000
HidP_Output = 1
HidP_Feature = 2

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
hd = ctypes.WinDLL('hid', use_last_error=True)
setup = ctypes.WinDLL('setupapi', use_last_error=True)

k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [wintypes.HANDLE]

hd.HidD_GetHidGuid.argtypes = [ctypes.c_void_p]
hd.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hd.HidD_GetPreparsedData.restype = wintypes.BOOL
hd.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]

setup.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setup.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
                                       ctypes.c_void_p, wintypes.DWORD]
setup.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]


class GUID(ctypes.Structure):
    _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                ('Data3', wintypes.WORD), ('Data4', ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('InterfaceClassGuid', GUID),
                ('Flags', wintypes.DWORD), ('Reserved', ctypes.c_void_p)]


setup.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p,
                                       ctypes.c_void_p, wintypes.DWORD]
setup.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                              ctypes.POINTER(GUID), wintypes.DWORD,
                                              ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setup.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p,
                                                   ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                   ctypes.c_void_p, wintypes.DWORD,
                                                   ctypes.POINTER(wintypes.DWORD),
                                                   ctypes.c_void_p]
setup.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL


# ---- HIDP_* 结构：必须与 hidpi.h 逐字段一致 ----
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


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ('Usage', wintypes.USHORT), ('UsagePage', wintypes.USHORT),
        ('InputReportByteLength', wintypes.USHORT),
        ('OutputReportByteLength', wintypes.USHORT),
        ('FeatureReportByteLength', wintypes.USHORT),
        ('Reserved', wintypes.USHORT * 17),
        ('NumberLinkCollectionNodes', wintypes.USHORT),
        ('NumberInputButtonCaps', wintypes.USHORT),
        ('NumberInputValueCaps', wintypes.USHORT),
        ('NumberInputDataIndices', wintypes.USHORT),
        ('NumberOutputButtonCaps', wintypes.USHORT),
        ('NumberOutputValueCaps', wintypes.USHORT),
        ('NumberOutputDataIndices', wintypes.USHORT),
        ('NumberFeatureButtonCaps', wintypes.USHORT),
        ('NumberFeatureValueCaps', wintypes.USHORT),
        ('NumberFeatureDataIndices', wintypes.USHORT),
    ]


hd.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hd.HidP_GetCaps.restype = ctypes.c_long
hd.HidP_GetValueCaps.argtypes = [ctypes.c_ubyte, ctypes.POINTER(HIDP_VALUE_CAPS),
                                 ctypes.POINTER(wintypes.USHORT), ctypes.c_void_p]
hd.HidP_GetValueCaps.restype = ctypes.c_long


def enum_paths():
    g = GUID()
    hd.HidD_GetHidGuid(ctypes.byref(g))
    s = setup.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)
    if not s or s == INVALID:
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
                    out.append(ctypes.wstring_at(ctypes.addressof(buf) + 4))
            i += 1
    finally:
        setup.SetupDiDestroyDeviceInfoList(s)
    return out


def get_value_caps(pp, rtype):
    cnt = wintypes.USHORT(0)
    hd.HidP_GetValueCaps(rtype, None, ctypes.byref(cnt), pp)
    if cnt.value == 0:
        return [], 0x00110000
    buf = (HIDP_VALUE_CAPS * cnt.value)()
    st = hd.HidP_GetValueCaps(rtype, buf, ctypes.byref(cnt), pp)
    res = []
    if (st & 0xFFFFFFFF) == HIDP_STATUS_SUCCESS:
        for i in range(cnt.value):
            c = buf[i]
            umin, umax = ((c.u.Range.UsageMin, c.u.Range.UsageMax) if c.IsRange
                          else (c.u.NotRange.Usage, c.u.NotRange.Usage))
            res.append({'RID': c.ReportID, 'UP': c.UsagePage, 'UMin': umin, 'UMax': umax,
                        'LinkUsage': c.LinkUsage, 'LinkUP': c.LinkUsagePage,
                        'LogMin': c.LogicalMin, 'LogMax': c.LogicalMax,
                        'PhysMin': c.PhysicalMin, 'PhysMax': c.PhysicalMax,
                        'BitSize': c.BitSize, 'Count': c.ReportCount})
    return res, (st & 0xFFFFFFFF)


def read_col(path):
    h = k32.CreateFileW(path, 0, 3, None, 3, 0, None)
    if not h or h == INVALID:
        return None, "CreateFile err=%d" % ctypes.get_last_error()
    try:
        pp = ctypes.c_void_p()
        if not hd.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            return None, "GetPreparsedData err=%d" % ctypes.get_last_error()
        try:
            caps = HIDP_CAPS()
            if (hd.HidP_GetCaps(pp, ctypes.byref(caps)) & 0xFFFFFFFF) != HIDP_STATUS_SUCCESS:
                return None, "GetCaps failed"
            feat, fst = get_value_caps(pp, HidP_Feature)
            outv, ost = get_value_caps(pp, HidP_Output)
            return {
                'UP': caps.UsagePage, 'U': caps.Usage,
                'in_len': caps.InputReportByteLength,
                'out_len': caps.OutputReportByteLength,
                'feat_len': caps.FeatureReportByteLength,
                'n_feat': caps.NumberFeatureValueCaps,
                'n_out': caps.NumberOutputValueCaps,
                'FEATURE': feat, 'FEATURE_st': hex(fst),
                'OUTPUT': outv, 'OUTPUT_st': hex(ost),
            }, None
        finally:
            hd.HidD_FreePreparsedData(pp)
    finally:
        k32.CloseHandle(h)


def col_tag(path):
    low = path.lower()
    for c in ('col01', 'col02', 'col03', 'col04'):
        if c in low:
            return c.upper()
    return path.split('#')[1] if '#' in path else path


# ---- goodhaptic 参考表 ----
GH = [
    (0x0E, 0x23, "触觉强度 Intensity（★ 最关键）"),
    (0x0D, 0xB0, "点击力度阈值 ButtonPressThreshold"),
    (0x0D, 0x52, "Input Mode"),
    (0x0D, 0x60, "Latency Mode"),
    (0x0D, 0x55, "Contact Count Max"),
    (0x0D, 0x59, "Pad Type"),
    (0xFF00, 0xC4, "Vendor 固件命令"),
    (0xFF00, 0xC5, "Vendor 初始化 blob"),
    (0xFF00, 0xC6, "Vendor 大块配置"),
    (0xFF00, 0xC7, "Vendor 状态"),
]


def main():
    as_json = '--json' in sys.argv
    # ★ 注意：设备接口路径里出现的是硬件 ID 串 "gxtp5100"，不是 "27c6"
    #   （VID 27C6 只在 \?\HID#VID_27C6&PID_01E9... 形式的 hardware id 里，
    #    而 SetupDiGetClassDevs 返回的 interface path 用的是 hwid 里第一个 token）
    paths = [p for p in enum_paths()
             if 'gxtp5100' in p.lower() or '27c6' in p.lower()]
    report = {}
    for p in sorted(paths, key=col_tag):
        info, err = read_col(p)
        report[col_tag(p)] = {'path': p, 'err': err, **(info or {})}

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=" * 104)
    print("### 本机 27C6 集合 · Feature / Output value caps 全表（只读 access=0，不发报文）")
    print("=" * 104)
    for tag in sorted(report):
        d = report[tag]
        print("\n" + "-" * 104)
        print("集合 %s" % tag)
        if d.get('err'):
            print("    <失败: %s>" % d['err'])
            continue
        print("    UP=0x%04X U=0x%04X   In/Out/Feat = %d/%d/%d   声明 caps: feat=%d out=%d"
              % (d['UP'], d['U'], d['in_len'], d['out_len'], d['feat_len'],
                 d['n_feat'], d['n_out']))
        for bucket in ('FEATURE', 'OUTPUT'):
            lst = d.get(bucket) or []
            print("    [%s] 实取 %d 条  status=%s" % (bucket, len(lst), d.get(bucket + '_st')))
            for e in lst:
                print("        RID=0x%02X  UP=0x%04X  U=0x%04X  logi[%d..%d]  phys[%d..%d]  %dbit ×%d  linkUP=0x%04X/linkU=0x%04X"
                      % (e['RID'], e['UP'], e['UMin'], e['LogMin'], e['LogMax'],
                         e['PhysMin'], e['PhysMax'], e['BitSize'], e['Count'],
                         e['LinkUP'], e['LinkUsage']))

    present_f = set()
    present_o = set()
    for tag, d in report.items():
        for e in (d.get('FEATURE') or []):
            present_f.add((e['UP'], e['UMin']))
        for e in (d.get('OUTPUT') or []):
            present_o.add((e['UP'], e['UMin']))

    print("\n" + "=" * 104)
    print("### 与 goodhaptic（GXTP5100 / ThinkBook 16 G8+ IPD）对照")
    print("=" * 104)
    print("  本机 FEATURE 出现的 (UP, Usage)：")
    for up, u in sorted(present_f):
        print("      (0x%04X, 0x%04X)" % (up, u))
    print("  本机 OUTPUT  出现的 (UP, Usage)：")
    for up, u in sorted(present_o):
        print("      (0x%04X, 0x%04X)" % (up, u))
    print("\n  goodhaptic 的关键 usage：")
    for up, u, desc in GH:
        in_f = (up, u) in present_f
        in_o = (up, u) in present_o
        mark = "✅FEATURE" if in_f else ("✅OUTPUT" if in_o else "❌无")
        print("      %-10s (0x%04X, 0x%04X)  %s" % (mark, up, u, desc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
