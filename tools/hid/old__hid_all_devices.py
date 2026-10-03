"""枚举本机全部 HID 顶层集合（含 usage page），用于发现传感器类设备。"""
import ctypes
from ctypes import wintypes

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)

class GUID(ctypes.Structure):
    _fields_ = [("D1", ctypes.c_ulong), ("D2", ctypes.c_ushort), ("D3", ctypes.c_ushort), ("D4", ctypes.c_ubyte * 8)]

class SP_DID(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wintypes.DWORD),
                ("R", ctypes.POINTER(ctypes.c_ulong))]

class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", ctypes.c_ushort), ("UsagePage", ctypes.c_ushort),
                ("InLen", ctypes.c_ushort), ("OutLen", ctypes.c_ushort), ("FeatLen", ctypes.c_ushort),
                ("Res", ctypes.c_ushort * 17),
                ("LinkColl", ctypes.c_ushort), ("InBtn", ctypes.c_ushort), ("InVal", ctypes.c_ushort),
                ("InDI", ctypes.c_ushort), ("OutBtn", ctypes.c_ushort), ("OutVal", ctypes.c_ushort),
                ("OutDI", ctypes.c_ushort), ("FeatBtn", ctypes.c_ushort), ("FeatVal", ctypes.c_ushort),
                ("FeatDI", ctypes.c_ushort)]

setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
                                                 wintypes.DWORD, ctypes.POINTER(SP_DID)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DID), ctypes.c_void_p,
                                                      wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]
hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidD_GetProductString.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]

PAGE = {0x01: "Generic Desktop", 0x0C: "Consumer", 0x0D: "Digitizer", 0xFF00: "VENDOR", 0x20: "★Sensor",
        0x0E: "Haptics", 0x80: "Power", 0x84: "Power", 0x08: "LED", 0x09: "Button", 0x06: "Generic Device",
        0xFF01: "VENDOR", 0xFF02: "VENDOR", 0xFF0F: "VENDOR", 0xFFBC: "VENDOR", 0x02: "Simulation"}

g = GUID()
hid.HidD_GetHidGuid(ctypes.byref(g))
hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)
i = 0
rows = []
while True:
    d = SP_DID()
    d.cbSize = ctypes.sizeof(d)
    if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(g), i, ctypes.byref(d)):
        break
    i += 1
    need = wintypes.DWORD(0)
    setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(d), None, 0, ctypes.byref(need), None)
    buf = ctypes.create_string_buffer(need.value)
    ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
    if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(d), buf, need.value, None, None):
        continue
    path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
    h = k32.CreateFileW(path, 0, 3, None, 3, 0, None)
    page = usage = None
    prod = ""
    if h and h != 0xFFFFFFFFFFFFFFFF:
        pp = ctypes.c_void_p()
        if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)) and pp.value:
            c = HIDP_CAPS()
            hid.HidP_GetCaps(pp, ctypes.byref(c))
            page, usage = c.UsagePage, c.Usage
        pb = ctypes.create_unicode_buffer(128)
        if hid.HidD_GetProductString(h, pb, 256):
            prod = pb.value
        k32.CloseHandle(h)
    rows.append((path, page, usage, prod))
setupapi.SetupDiDestroyDeviceInfoList(hdev)

print("HID 顶层集合总数 = %d\n" % len(rows))
for path, page, usage, prod in rows:
    short = path.split("#")[1][:46] if "#" in path else path[:46]
    tag = PAGE.get(page or 0, "page 0x%04X" % (page or 0))
    print("   %-48s %-16s usage=0x%04X  %s" % (short, tag, usage or 0, prod))

print("\n=== ★ 传感器类（page 0x20）===")
found = False
for path, page, usage, prod in rows:
    if page == 0x20:
        print("   ★", path)
        found = True
if not found:
    print("   （本机未枚举到任何 HID Sensor（page 0x20）设备）")
