"""通过 SetupAPI + IOCTL_HID_GET_REPORT_DESCRIPTOR 抓所有 HID 设备的 report descriptor。"""
import ctypes, sys, json
from ctypes import wintypes

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid      = ctypes.WinDLL("hid", use_last_error=True)
k32      = ctypes.WinDLL("kernel32", use_last_error=True)

class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte*8)]
class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.POINTER(ctypes.c_ulong))]
class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("ClassGuid", GUID),
                ("DevInst", wintypes.DWORD), ("Reserved", ctypes.POINTER(ctypes.c_ulong))]

DIGCF_PRESENT = 0x2; DIGCF_DEVICEINTERFACE = 0x10
IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000B0192
GENERIC_READ = 0x80000000; GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3; FILE_SHARE_RW = 3

g = GUID(); hid.HidD_GetHidGuid(ctypes.byref(g))
hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
if hdev == -1: print("SetupDiGetClassDevs 失败"); sys.exit(1)

i = 0; results = []
while True:
    did = SP_DEVICE_INTERFACE_DATA(); did.cbSize = ctypes.sizeof(did)
    if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(g), i, ctypes.byref(did)):
        break
    i += 1
    need = wintypes.DWORD(0)
    setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(did), None, 0, ctypes.byref(need), None)
    buf = ctypes.create_string_buffer(need.value)
    ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p)==8 else 6
    if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(did), buf, need.value, None, None):
        continue
    path = ctypes.wstring_at(ctypes.addressof(buf)+4)
    if "gxtp5100" not in path.lower() and "27c6" not in path.lower():
        continue
    h = k32.CreateFileW(path, GENERIC_READ|GENERIC_WRITE, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    if h in (-1, 0xFFFFFFFFFFFFFFFF):
        h = k32.CreateFileW(path, 0, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    if h in (-1, 0xFFFFFFFFFFFFFFFF):
        results.append({"path": path, "err": ctypes.get_last_error()}); continue
    # report descriptor
    n = 4096; buf2 = (ctypes.c_ubyte*n)(); got = wintypes.DWORD(0)
    ok = k32.DeviceIoControl(h, IOCTL_HID_GET_REPORT_DESCRIPTOR, None, 0, buf2, n, ctypes.byref(got), None)
    desc = bytes(buf2[:got.value]) if ok else None
    # preparsed data + caps
    pp = ctypes.c_void_p()
    caps = {}
    if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
        class HIDP_CAPS(ctypes.Structure):
            _fields_ = [("Usage", ctypes.c_ushort), ("UsagePage", ctypes.c_ushort),
                        ("InputReportByteLength", ctypes.c_ushort), ("OutputReportByteLength", ctypes.c_ushort),
                        ("FeatureReportByteLength", ctypes.c_ushort), ("Reserved", ctypes.c_ushort*17),
                        ("NumberLinkCollectionNodes", ctypes.c_ushort), ("NumberInputButtonCaps", ctypes.c_ushort),
                        ("NumberInputValueCaps", ctypes.c_ushort), ("NumberInputDataIndices", ctypes.c_ushort),
                        ("NumberOutputButtonCaps", ctypes.c_ushort), ("NumberOutputValueCaps", ctypes.c_ushort),
                        ("NumberOutputDataIndices", ctypes.c_ushort), ("NumberFeatureButtonCaps", ctypes.c_ushort),
                        ("NumberFeatureValueCaps", ctypes.c_ushort), ("NumberFeatureDataIndices", ctypes.c_ushort)]
        c = HIDP_CAPS()
        hid.HidP_GetCaps(pp, ctypes.byref(c))
        caps = {"Usage":hex(c.Usage),"UsagePage":hex(c.UsagePage),
                "InLen":c.InputReportByteLength,"OutLen":c.OutputReportByteLength,"FeatLen":c.FeatureReportByteLength,
                "LinkColl":c.NumberLinkCollectionNodes,
                "InBtn":c.NumberInputButtonCaps,"InVal":c.NumberInputValueCaps,
                "OutBtn":c.NumberOutputButtonCaps,"OutVal":c.NumberOutputValueCaps,
                "FeatBtn":c.NumberFeatureButtonCaps,"FeatVal":c.NumberFeatureValueCaps}
        hid.HidD_FreePreparsedData(pp)
    k32.CloseHandle(h)
    results.append({"path": path, "desc": desc.hex() if desc else None, "desclen": len(desc) if desc else 0, "caps": caps})
setupapi.SetupDiDestroyDeviceInfoList(hdev)
json.dump(results, open("hid_devices.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("找到 %d 个 GXTP5100 HID 接口\n"%len(results))
for r in results:
    print("="*74)
    print(r["path"])
    if "err" in r: print("   打开失败 err=%d"%r["err"]); continue
    print("   descriptor 长度 = %d 字节"%r["desclen"])
    print("   caps = %s"%r["caps"])
    if r["desc"]:
        d=bytes.fromhex(r["desc"])
        for k in range(0,min(len(d),256),16):
            print("     %04X  %s"%(k," ".join("%02X"%c for c in d[k:k+16])))
