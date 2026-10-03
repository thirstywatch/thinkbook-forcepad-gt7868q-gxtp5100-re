# -*- coding: utf-8 -*-
"""haptic_caps.py — 完整 HID caps 测绘（只读）

为什么写它：
  AllCaps.cs 注释承认「Col02 的 Feature RID 6/7/11/12/13 从未被看过内容」。
  微软 HID 触觉规范说 SimpleHapticsController 是 PTP 顶层集合的【子集合】，
  这意味着 Manual Trigger / Auto Trigger 的 Feature/Output 报告
  会挂在 Col01 上，而不是 Col04。项目此前把 Col04 当主战场，可能漏了 Col01。

本脚本做四件事（全部只读）：
  1. 枚举全部 GXTP5100 HID 接口（不写死 Col01..Col04）
  2. 每个接口：顶层 caps（usage page/usage + 三种报告长度 + 集合节点数）
  3. 每个接口：枚举【全部】link collection node（找出 0x0E/0x01 SHC 等）
  4. 每个接口：枚举【全部】value caps（Input/Output/Feature），打印 RID + usage + 范围
  5. 顺带 dump 原始 report descriptor 到文件（找 0x0E 页出现的上下文）

用法： python haptic_caps.py
输出： poc/haptic_caps.txt （同时打印到 stdout）
"""
import ctypes, sys, os, time
from ctypes import wintypes

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "haptic_caps.txt")
GUID_STR = "{4d1e55b2-f16f-11cf-88cb-001111000030}"
DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID = ctypes.c_void_p(-1).value
HIDP_STATUS_SUCCESS = 0x00110000
IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000B0190

setupapi = ctypes.WinDLL('setupapi', use_last_error=True)
hid = ctypes.WinDLL('hid', use_last_error=True)
k32 = ctypes.WinDLL('kernel32', use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.c_void_p)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [('Usage', wintypes.USHORT), ('UsagePage', wintypes.USHORT),
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
                ('NumberFeatureDataIndices', wintypes.USHORT)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", wintypes.USHORT), ("ReportID", ctypes.c_ubyte),
                ("IsAlias", ctypes.c_ubyte), ("BitField", wintypes.USHORT),
                ("LinkCollection", wintypes.USHORT), ("LinkUsage", wintypes.USHORT),
                ("LinkUsagePage", wintypes.USHORT),
                ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte),
                ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
                ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte),
                ("BitSize", wintypes.USHORT), ("ReportCount", wintypes.USHORT),
                ("R2a", wintypes.USHORT), ("R2b", wintypes.USHORT),
                ("R2c", wintypes.USHORT), ("R2d", wintypes.USHORT),
                ("R2e", wintypes.USHORT),
                ("UnitsExp", wintypes.ULONG), ("Units", wintypes.ULONG),
                ("LogicalMin", wintypes.LONG), ("LogicalMax", wintypes.LONG),
                ("PhysicalMin", wintypes.LONG), ("PhysicalMax", wintypes.LONG),
                ("UsageMin", wintypes.USHORT), ("UsageMax", wintypes.USHORT),
                ("StringMin", wintypes.USHORT), ("StringMax", wintypes.USHORT),
                ("DesignatorMin", wintypes.USHORT), ("DesignatorMax", wintypes.USHORT),
                ("DataIndexMin", wintypes.USHORT), ("DataIndexMax", wintypes.USHORT)]


class HIDP_LINK_COLLECTION_NODE(ctypes.Structure):
    _fields_ = [("LinkUsage", wintypes.USHORT), ("LinkUsagePage", wintypes.USHORT),
                ("Parent", wintypes.USHORT), ("NumberOfChildren", wintypes.USHORT),
                ("NextSibling", wintypes.USHORT), ("FirstChild", wintypes.USHORT),
                ("bits", wintypes.ULONG), ("UserContext", ctypes.c_void_p)]


setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p,
                                         ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                 ctypes.POINTER(GUID), wintypes.DWORD,
                                                 ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p,
                                                      ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      ctypes.c_void_p, wintypes.DWORD,
                                                      ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                  ctypes.POINTER(wintypes.USHORT), ctypes.c_void_p]
hid.HidP_GetLinkCollectionNodes.argtypes = [ctypes.c_void_p,
                                            ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p]


def guid_from_string(s):
    g = GUID()
    ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
    return g


def enum_paths(filter_sub="GXTP5100"):
    out = []
    g = guid_from_string(GUID_STR)
    s = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None,
                                      DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not s or s == INVALID:
        return out
    try:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        i = 0
        while setupapi.SetupDiEnumDeviceInterfaces(s, None, ctypes.byref(g), i, ctypes.byref(did)):
            i += 1
            req = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(s, ctypes.byref(did), None, 0,
                                                      ctypes.byref(req), None)
            if req.value == 0:
                continue
            buf = ctypes.create_string_buffer(req.value)
            ctypes.memset(buf, 0, req.value)
            cb = wintypes.DWORD(8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            ctypes.memmove(buf, ctypes.byref(cb), 4)
            if setupapi.SetupDiGetDeviceInterfaceDetailW(s, ctypes.byref(did), buf,
                                                         req.value, ctypes.byref(req), None):
                p = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                if p and (filter_sub is None or filter_sub.lower() in p.lower()):
                    out.append(p)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(s)
    return out


def short_col(path):
    """从接口路径里抽出 GXTP5100&ColNN 这一段"""
    up = path.upper()
    k = up.find("GXTP5100&")
    if k < 0:
        return path
    j = path.find("#", k)
    return path[k:j] if j > 0 else path[k:]


LINES = []


def out(s=""):
    LINES.append(s)
    print(s)


def dump_value_caps(pp, caps, kind, kindname):
    n = (caps.NumberInputValueCaps, caps.NumberOutputValueCaps,
         caps.NumberFeatureValueCaps)[kind]
    if n == 0:
        out("    %-7s (none)" % kindname)
        return
    ln = n + 8
    sz = ctypes.sizeof(HIDP_VALUE_CAPS)
    buf = ctypes.create_string_buffer(sz * ln)
    l = wintypes.USHORT(ln)
    st = hid.HidP_GetValueCaps(kind, buf, ctypes.byref(l), pp)
    if st != HIDP_STATUS_SUCCESS:
        out("    %-7s HidP_GetValueCaps -> 0x%08X" % (kindname, st & 0xFFFFFFFF))
        return
    for i in range(l.value):
        v = HIDP_VALUE_CAPS.from_buffer_copy(buf.raw[i * sz:(i + 1) * sz])
        if v.IsRange:
            usage = "0x%04X/0x%04X-0x%04X" % (v.UsagePage, v.UsageMin, v.UsageMax)
        else:
            usage = "0x%04X/0x%04X" % (v.UsagePage, v.UsageMin)
        out("    %-7s RID=%-3d %-22s bit=%-3d cnt=%-3d log=%d..%d phys=%d..%d units=0x%08X exp=%d lc=%d abs=%d null=%d" % (
            kindname, v.ReportID, usage, v.BitSize, v.ReportCount,
            v.LogicalMin, v.LogicalMax, v.PhysicalMin, v.PhysicalMax,
            v.Units, v.UnitsExp, v.LinkCollection, v.IsAbsolute, v.HasNull))


def probe(path, idx):
    out("")
    out("=" * 78)
    out("[%d] %s" % (idx, short_col(path)))
    out("=" * 78)
    h = k32.CreateFileW(path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                        OPEN_EXISTING, 0, None)
    if not h or h == INVALID:
        h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                            None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID:
        out("  CreateFile err=%d" % ctypes.get_last_error())
        return
    try:
        pp = ctypes.c_void_p()
        if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            out("  HidD_GetPreparsedData err=%d" % ctypes.get_last_error())
            return
        try:
            c = HIDP_CAPS()
            if hid.HidP_GetCaps(pp, ctypes.byref(c)) != HIDP_STATUS_SUCCESS:
                out("  HidP_GetCaps failed")
                return
            out("  TOP: UP=0x%04X U=0x%04X  In=%d Out=%d Feat=%d  LinkColl=%d" % (
                c.UsagePage, c.Usage, c.InputReportByteLength,
                c.OutputReportByteLength, c.FeatureReportByteLength,
                c.NumberLinkCollectionNodes))
            # 集合节点
            nn = c.NumberLinkCollectionNodes
            if nn:
                nl = wintypes.ULONG(nn)
                nb = ctypes.create_string_buffer(ctypes.sizeof(HIDP_LINK_COLLECTION_NODE) * nn)
                if hid.HidP_GetLinkCollectionNodes(nb, ctypes.byref(nl), pp) == HIDP_STATUS_SUCCESS:
                    sz = ctypes.sizeof(HIDP_LINK_COLLECTION_NODE)
                    out("  LINK COLLECTION NODES (%d):" % nl.value)
                    for i in range(nl.value):
                        nd = HIDP_LINK_COLLECTION_NODE.from_buffer_copy(nb.raw[i * sz:(i + 1) * sz])
                        ctype = nd.bits & 0xFF
                        out("    lc=%-3d parent=%-3d %-3s UP=0x%04X U=0x%04X children=%d" % (
                            i, nd.Parent,
                            "<TOP>" if nd.Parent == 0xFFFF or nd.Parent == 0 else "",
                            nd.LinkUsagePage, nd.LinkUsage, nd.NumberOfChildren))
            out("  ---- value caps ----")
            dump_value_caps(pp, c, 0, "Input")
            dump_value_caps(pp, c, 1, "Output")
            dump_value_caps(pp, c, 2, "Feature")
        finally:
            hid.HidD_FreePreparsedData(pp)
        # report descriptor
        tmp = ctypes.create_string_buffer(8192)
        ret = wintypes.DWORD(0)
        ok = k32.DeviceIoControl(h, IOCTL_HID_GET_REPORT_DESCRIPTOR, None, 0,
                                 tmp, 8192, ctypes.byref(ret), None)
        if ok and ret.value > 0:
            rd = tmp.raw[:ret.value]
            fn = os.path.join(os.path.dirname(OUT), "rdesc_%s.bin" % short_col(path).replace("&", "_").replace("#", "-"))
            with open(fn, "wb") as f:
                f.write(rd)
            out("  RDESC: %d bytes -> %s" % (len(rd), os.path.basename(fn)))
            # 找 usage page 0x0E 出现的位置（05 0E | 06 0E 00）
            hits = []
            for i in range(len(rd) - 1):
                if rd[i] == 0x05 and rd[i + 1] == 0x0E:
                    hits.append("off %d: 05 0E (1B page)" % i)
                if rd[i] == 0x06 and i + 2 < len(rd) and rd[i + 1] == 0x0E and rd[i + 2] == 0x00:
                    hits.append("off %d: 06 0E 00 (2B page)" % i)
            out("  RDESC usage-page-0x0E hits: %s" % (", ".join(hits) if hits else "NONE"))
            for k in ("0x0E", "0e", "HAPTIC"):
                pass
        else:
            out("  RDESC: DeviceIoControl fail err=%d" % ctypes.get_last_error())
    finally:
        k32.CloseHandle(h)


def main():
    paths = enum_paths("GXTP5100")
    out("GXTP5100 HID 接口数量 = %d" % len(paths))
    for p in paths:
        out("  - %s" % short_col(p))
    for i, p in enumerate(paths, 1):
        try:
            probe(p, i)
        except Exception as e:
            out("  EXCEPTION: %r" % (e,))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    print("\n[written] %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
