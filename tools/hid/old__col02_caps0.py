"""col02_caps0.py —— 用 access=0 的句柄绕过 PTP 独占，拿 Col02/Col03 的**全部 caps（尤其 Feature）**。
目的：查 usage page 0x0E（Haptics）与 page 0x0D（Digitizers）里到底声明了哪些字段，
      特别是 0x0D/0xB0 Button Press Threshold（力度阈值旋钮）—— 微软规范说 device-initiated 设备可支持它。
纯读：只 CreateFile + HidD_GetPreparsedData + HidP_Get*Caps，不发任何命令。
"""
import ctypes, json, sys
from ctypes import wintypes

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)

class GUID(ctypes.Structure):
    _fields_ = [("D1", ctypes.c_ulong), ("D2", ctypes.c_ushort), ("D3", ctypes.c_ushort), ("D4", ctypes.c_ubyte * 8)]
class SP_DID(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wintypes.DWORD), ("R", ctypes.POINTER(ctypes.c_ulong))]
class SP_DETAIL(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("Path", ctypes.c_wchar * 1)]
class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", ctypes.c_ushort), ("UsagePage", ctypes.c_ushort),
                ("InLen", ctypes.c_ushort), ("OutLen", ctypes.c_ushort), ("FeatLen", ctypes.c_ushort), ("Res", ctypes.c_ushort * 17),
                ("LinkColl", ctypes.c_ushort), ("InBtn", ctypes.c_ushort), ("InVal", ctypes.c_ushort), ("InDI", ctypes.c_ushort),
                ("OutBtn", ctypes.c_ushort), ("OutVal", ctypes.c_ushort), ("OutDI", ctypes.c_ushort),
                ("FeatBtn", ctypes.c_ushort), ("FeatVal", ctypes.c_ushort), ("FeatDI", ctypes.c_ushort)]
class VCAPS(ctypes.Structure):
    _fields_ = [("UsagePage", ctypes.c_ushort), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
                ("BitField", ctypes.c_ushort), ("LinkCollection", ctypes.c_ushort), ("LinkUsage", ctypes.c_ushort), ("LinkUsagePage", ctypes.c_ushort),
                ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
                ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte), ("BitSize", ctypes.c_ushort), ("ReportCount", ctypes.c_ushort),
                ("Reserved2", ctypes.c_ushort * 5), ("UnitsExp", ctypes.c_ulong), ("Units", ctypes.c_ulong),
                ("LogicalMin", ctypes.c_long), ("LogicalMax", ctypes.c_long), ("PhysicalMin", ctypes.c_long), ("PhysicalMax", ctypes.c_long),
                ("UsageMin", ctypes.c_ushort), ("UsageMax", ctypes.c_ushort),
                ("StringMin", ctypes.c_ushort), ("StringMax", ctypes.c_ushort),
                ("DesignatorMin", ctypes.c_ushort), ("DesignatorMax", ctypes.c_ushort),
                ("DataIndexMin", ctypes.c_ushort), ("DataIndexMax", ctypes.c_ushort)]
class BCAPS(ctypes.Structure):
    _fields_ = [("UsagePage", ctypes.c_ushort), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
                ("BitField", ctypes.c_ushort), ("LinkCollection", ctypes.c_ushort), ("LinkUsage", ctypes.c_ushort), ("LinkUsagePage", ctypes.c_ushort),
                ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
                ("ReportCount", ctypes.c_ushort), ("Reserved", ctypes.c_ushort * 9),
                ("UsageMin", ctypes.c_ushort), ("UsageMax", ctypes.c_ushort),
                ("StringMin", ctypes.c_ushort), ("StringMax", ctypes.c_ushort),
                ("DesignatorMin", ctypes.c_ushort), ("DesignatorMax", ctypes.c_ushort),
                ("DataIndexMin", ctypes.c_ushort), ("DataIndexMax", ctypes.c_ushort)]

setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DID)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DID), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(VCAPS), ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
hid.HidP_GetButtonCaps.argtypes = [ctypes.c_int, ctypes.POINTER(BCAPS), ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]

INVALID = 0xFFFFFFFFFFFFFFFF
TYPE = {0: "Input", 1: "Output", 2: "Feature"}

g = GUID(); hid.HidD_GetHidGuid(ctypes.byref(g))
hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)

paths = []
i = 0
while True:
    did = SP_DID(); did.cbSize = ctypes.sizeof(did)
    if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(g), i, ctypes.byref(did)):
        break
    i += 1
    need = wintypes.DWORD(0)
    setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(did), None, 0, ctypes.byref(need), None)
    if need.value:
        buf = ctypes.create_string_buffer(need.value + 8)
        ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        if setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(did), buf, need.value, None, None):
            p = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            if "gxtp5100" in p.lower():
                paths.append(p)

print("GXTP5100 接口 %d 个\n" % len(paths))
out = {}
for p in paths:
    tag = p.split("#")[1] if "#" in p else p
    print("=" * 78)
    print(tag)
    h = None
    for acc, share, note in ((0, 3, "acc=0/share=3"), (0, 1, "acc=0/share=1"), (0, 0, "acc=0/share=0")):
        h = k32.CreateFileW(p, acc, share, None, 3, 0, None)
        if h and h != INVALID:
            print("  打开成功：%s" % note); break
        print("  %s -> err=%d" % (note, ctypes.get_last_error())); h = None
    if not h:
        continue
    pp = ctypes.c_void_p()
    if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)) or not pp.value:
        print("  HidD_GetPreparsedData 失败 err=%d" % ctypes.get_last_error())
        k32.CloseHandle(h); continue
    c = HIDP_CAPS(); hid.HidP_GetCaps(pp, ctypes.byref(c))
    print("  UsagePage=0x%04X Usage=0x%04X  In=%d Out=%d Feat=%d  LinkColl=%d" % (c.UsagePage, c.Usage, c.InLen, c.OutLen, c.FeatLen, c.LinkColl))
    rec = {"path": p, "caps": {"up": c.UsagePage, "u": c.Usage, "In": c.InLen, "Out": c.OutLen, "Feat": c.FeatLen}, "fields": []}
    for t in (0, 1, 2):
        cnt = ctypes.c_ulong(128); arr = (VCAPS * 128)()
        hid.HidP_GetValueCaps(t, arr, ctypes.byref(cnt), pp)
        if cnt.value:
            print("   --- %s 值字段 %d 个 ---" % (TYPE[t], cnt.value))
            for k in range(cnt.value):
                v = arr[k]
                rng = ("0x%04X..0x%04X" % (v.UsageMin, v.UsageMax)) if v.IsRange else "0x%04X" % v.UsageMin
                print("      RID=%-3d page=0x%04X usage=%-12s BitOff=%-5d BitSize=%-3d Cnt=%-3d %s..%s" % (
                    v.ReportID, v.UsagePage, rng, v.BitField, v.BitSize, v.ReportCount, v.LogicalMin, v.LogicalMax))
                rec["fields"].append({"type": TYPE[t], "kind": "value", "RID": v.ReportID, "page": v.UsagePage,
                                      "usage": rng, "bitoff": v.BitField, "bitsize": v.BitSize, "count": v.ReportCount,
                                      "lmin": v.LogicalMin, "lmax": v.LogicalMax, "linkusage": v.LinkUsage})
        cnt2 = ctypes.c_ulong(128); arr2 = (BCAPS * 128)()
        hid.HidP_GetButtonCaps(t, arr2, ctypes.byref(cnt2), pp)
        if cnt2.value:
            print("   --- %s 按钮字段 %d 个 ---" % (TYPE[t], cnt2.value))
            for k in range(cnt2.value):
                b = arr2[k]
                rng = ("0x%04X..0x%04X" % (b.UsageMin, b.UsageMax)) if b.IsRange else "0x%04X" % b.UsageMin
                print("      RID=%-3d page=0x%04X usage=%-12s BitOff=%-5d Cnt=%d" % (b.ReportID, b.UsagePage, rng, b.BitField, b.ReportCount))
                rec["fields"].append({"type": TYPE[t], "kind": "button", "RID": b.ReportID, "page": b.UsagePage,
                                      "usage": rng, "bitoff": b.BitField, "count": b.ReportCount, "linkusage": b.LinkUsage})
    hid.HidD_FreePreparsedData(pp)
    k32.CloseHandle(h)
    out[tag] = rec

json.dump(out, open("caps-all.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已写 caps-all.json")
