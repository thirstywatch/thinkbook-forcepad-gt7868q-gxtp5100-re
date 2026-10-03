"""枚举触控板每个 HID collection 的字段级 caps（value/button × input/output/feature）。"""
import ctypes, json, sys
from ctypes import wintypes
setupapi=ctypes.WinDLL("setupapi",use_last_error=True); hid=ctypes.WinDLL("hid",use_last_error=True); k32=ctypes.WinDLL("kernel32",use_last_error=True)
class GUID(ctypes.Structure): _fields_=[("D1",ctypes.c_ulong),("D2",ctypes.c_ushort),("D3",ctypes.c_ushort),("D4",ctypes.c_ubyte*8)]
class SP_DID(ctypes.Structure):
    _fields_=[("cbSize",wintypes.DWORD),("InterfaceClassGuid",GUID),("Flags",wintypes.DWORD),("R",ctypes.POINTER(ctypes.c_ulong))]
class HIDP_CAPS(ctypes.Structure):
    _fields_=[("Usage",ctypes.c_ushort),("UsagePage",ctypes.c_ushort),
        ("InLen",ctypes.c_ushort),("OutLen",ctypes.c_ushort),("FeatLen",ctypes.c_ushort),("Res",ctypes.c_ushort*17),
        ("LinkColl",ctypes.c_ushort),("InBtn",ctypes.c_ushort),("InVal",ctypes.c_ushort),("InDI",ctypes.c_ushort),
        ("OutBtn",ctypes.c_ushort),("OutVal",ctypes.c_ushort),("OutDI",ctypes.c_ushort),
        ("FeatBtn",ctypes.c_ushort),("FeatVal",ctypes.c_ushort),("FeatDI",ctypes.c_ushort)]
class VCAPS(ctypes.Structure):
    _fields_=[("UsagePage",ctypes.c_ushort),("ReportID",ctypes.c_ubyte),("IsAlias",ctypes.c_ubyte),
        ("BitField",ctypes.c_ushort),("LinkCollection",ctypes.c_ushort),("LinkUsage",ctypes.c_ushort),("LinkUsagePage",ctypes.c_ushort),
        ("IsRange",ctypes.c_ubyte),("IsStringRange",ctypes.c_ubyte),("IsDesignatorRange",ctypes.c_ubyte),("IsAbsolute",ctypes.c_ubyte),
        ("HasNull",ctypes.c_ubyte),("Reserved",ctypes.c_ubyte),("BitSize",ctypes.c_ushort),("ReportCount",ctypes.c_ushort),
        ("Reserved2",ctypes.c_ushort*5),("UnitsExp",ctypes.c_ulong),("Units",ctypes.c_ulong),
        ("LogicalMin",ctypes.c_long),("LogicalMax",ctypes.c_long),("PhysicalMin",ctypes.c_long),("PhysicalMax",ctypes.c_long),
        ("UsageMin",ctypes.c_ushort),("UsageMax",ctypes.c_ushort),
        ("StringMin",ctypes.c_ushort),("StringMax",ctypes.c_ushort),
        ("DesignatorMin",ctypes.c_ushort),("DesignatorMax",ctypes.c_ushort),
        ("DataIndexMin",ctypes.c_ushort),("DataIndexMax",ctypes.c_ushort)]
class BCAPS(ctypes.Structure):
    _fields_=[("UsagePage",ctypes.c_ushort),("ReportID",ctypes.c_ubyte),("IsAlias",ctypes.c_ubyte),
        ("BitField",ctypes.c_ushort),("LinkCollection",ctypes.c_ushort),("LinkUsage",ctypes.c_ushort),("LinkUsagePage",ctypes.c_ushort),
        ("IsRange",ctypes.c_ubyte),("IsStringRange",ctypes.c_ubyte),("IsDesignatorRange",ctypes.c_ubyte),("IsAbsolute",ctypes.c_ubyte),
        ("ReportCount",ctypes.c_ushort),("Reserved",ctypes.c_ushort*9),
        ("UsageMin",ctypes.c_ushort),("UsageMax",ctypes.c_ushort),
        ("StringMin",ctypes.c_ushort),("StringMax",ctypes.c_ushort),
        ("DesignatorMin",ctypes.c_ushort),("DesignatorMax",ctypes.c_ushort),
        ("DataIndexMin",ctypes.c_ushort),("DataIndexMax",ctypes.c_ushort)]

setupapi.SetupDiGetClassDevsW.restype=ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes=[ctypes.POINTER(GUID),ctypes.c_wchar_p,ctypes.c_void_p,wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype=wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(GUID),wintypes.DWORD,ctypes.POINTER(SP_DID)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype=wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes=[ctypes.c_void_p,ctypes.POINTER(SP_DID),ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
k32.CreateFileW.restype=ctypes.c_void_p
k32.CreateFileW.argtypes=[ctypes.c_wchar_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
k32.DeviceIoControl.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
hid.HidD_GetHidGuid.argtypes=[ctypes.POINTER(GUID)]
hid.HidD_GetPreparsedData.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
hid.HidP_GetCaps.argtypes=[ctypes.c_void_p,ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.argtypes=[ctypes.c_int,ctypes.POINTER(VCAPS),ctypes.POINTER(ctypes.c_ulong),ctypes.c_void_p]
hid.HidP_GetButtonCaps.argtypes=[ctypes.c_int,ctypes.POINTER(BCAPS),ctypes.POINTER(ctypes.c_ulong),ctypes.c_void_p]

# 直接复用已抓到的路径
dev=json.load(open("hid_devices.json",encoding="utf-8"))
TYPE={0:"Input",1:"Output",2:"Feature"}
for r in dev:
    path=r["path"]
    h=k32.CreateFileW(path,0x80000000,3,None,3,0,None)
    if not h or h==0xFFFFFFFFFFFFFFFF:
        print("打开失败:",path, ctypes.get_last_error()); continue
    pp=ctypes.c_void_p()
    if not hid.HidD_GetPreparsedData(h,ctypes.byref(pp)) or not pp.value:
        print("preparsed 失败:",path); continue
    c=HIDP_CAPS(); hid.HidP_GetCaps(pp,ctypes.byref(c))
    print("="*78)
    print("%s\n   UsagePage=0x%04X Usage=0x%04X   In=%d Out=%d Feat=%d  LinkColl=%d"%(
        path.split('#')[1], c.UsagePage, c.Usage, c.InLen, c.OutLen, c.FeatLen, c.LinkColl))
    for t in (0,1,2):
        cnt=ctypes.c_ulong(64); arr=(VCAPS*64)()
        rc=hid.HidP_GetValueCaps(t,arr,ctypes.byref(cnt),pp)
        if cnt.value:
            print("   --- %s 值字段 %d 个 ---"%(TYPE[t],cnt.value))
            for i in range(min(cnt.value,40)):
                v=arr[i]
                rng = ("0x%04X..0x%04X"%(v.UsageMin,v.UsageMax)) if v.IsRange else "0x%04X"%v.UsageMin
                print("      RID=%-3d page=0x%04X usage=%-12s BitOff=%-5d BitSize=%-3d Count=%-3d %s..%s abs=%d null=%d"%(
                    v.ReportID,v.UsagePage,rng,v.BitField,v.BitSize,v.ReportCount,v.LogicalMin,v.LogicalMax,v.IsAbsolute,v.HasNull))
        cnt2=ctypes.c_ulong(64); arr2=(BCAPS*64)()
        rc2=hid.HidP_GetButtonCaps(t,arr2,ctypes.byref(cnt2),pp)
        if cnt2.value:
            print("   --- %s 按钮字段 %d 个 ---"%(TYPE[t],cnt2.value))
            for i in range(min(cnt2.value,20)):
                b=arr2[i]
                rng=("0x%04X..0x%04X"%(b.UsageMin,b.UsageMax)) if b.IsRange else "0x%04X"%b.UsageMin
                print("      RID=%-3d page=0x%04X usage=%-12s BitOff=%-5d Count=%d"%(b.ReportID,b.UsagePage,rng,b.BitField,b.ReportCount))
    k32.CloseHandle(h)
