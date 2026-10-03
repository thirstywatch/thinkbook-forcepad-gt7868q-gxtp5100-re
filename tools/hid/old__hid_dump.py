"""抓 HID report descriptor + caps。修正：SetupAPI 句柄必须用 c_void_p，否则被截断。"""
import ctypes, sys, json
from ctypes import wintypes
setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid      = ctypes.WinDLL("hid", use_last_error=True)
k32      = ctypes.WinDLL("kernel32", use_last_error=True)

class GUID(ctypes.Structure):
    _fields_=[("D1",ctypes.c_ulong),("D2",ctypes.c_ushort),("D3",ctypes.c_ushort),("D4",ctypes.c_ubyte*8)]
class SP_DID(ctypes.Structure):
    _fields_=[("cbSize",wintypes.DWORD),("InterfaceClassGuid",GUID),("Flags",wintypes.DWORD),
              ("Reserved",ctypes.POINTER(ctypes.c_ulong))]
class HIDP_CAPS(ctypes.Structure):
    _fields_=[("Usage",ctypes.c_ushort),("UsagePage",ctypes.c_ushort),
              ("InputReportByteLength",ctypes.c_ushort),("OutputReportByteLength",ctypes.c_ushort),
              ("FeatureReportByteLength",ctypes.c_ushort),("Reserved",ctypes.c_ushort*17),
              ("NumberLinkCollectionNodes",ctypes.c_ushort),("NumberInputButtonCaps",ctypes.c_ushort),
              ("NumberInputValueCaps",ctypes.c_ushort),("NumberInputDataIndices",ctypes.c_ushort),
              ("NumberOutputButtonCaps",ctypes.c_ushort),("NumberOutputValueCaps",ctypes.c_ushort),
              ("NumberOutputDataIndices",ctypes.c_ushort),("NumberFeatureButtonCaps",ctypes.c_ushort),
              ("NumberFeatureValueCaps",ctypes.c_ushort),("NumberFeatureDataIndices",ctypes.c_ushort)]

# ★ 关键：句柄/指针型返回值必须声明
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DID)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DID),
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes=[ctypes.c_void_p]
hid.HidD_GetHidGuid.argtypes=[ctypes.POINTER(GUID)]
hid.HidD_GetPreparsedData.argtypes=[ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidP_GetCaps.argtypes=[ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes=[ctypes.c_wchar_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
k32.DeviceIoControl.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]

g=GUID(); hid.HidD_GetHidGuid(ctypes.byref(g))
hdev=setupapi.SetupDiGetClassDevsW(ctypes.byref(g),None,None,0x12)   # PRESENT|DEVICEINTERFACE
print("HDEVINFO = 0x%X"%(hdev or 0))
i=0; res=[]
while True:
    d=SP_DID(); d.cbSize=ctypes.sizeof(d)
    if not setupapi.SetupDiEnumDeviceInterfaces(hdev,None,ctypes.byref(g),i,ctypes.byref(d)): break
    i+=1
    need=wintypes.DWORD(0)
    setupapi.SetupDiGetDeviceInterfaceDetailW(hdev,ctypes.byref(d),None,0,ctypes.byref(need),None)
    buf=ctypes.create_string_buffer(need.value)
    ctypes.cast(buf,ctypes.POINTER(wintypes.DWORD))[0]= 8 if ctypes.sizeof(ctypes.c_void_p)==8 else 6
    if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev,ctypes.byref(d),buf,need.value,None,None): continue
    path=ctypes.wstring_at(ctypes.addressof(buf)+4)
    if "gxtp5100" not in path.lower(): continue
    h=k32.CreateFileW(path,0x80000000|0x40000000,3,None,3,0,None)
    if not h or h==0xFFFFFFFFFFFFFFFF: h=k32.CreateFileW(path,0,3,None,3,0,None)
    if not h or h==0xFFFFFFFFFFFFFFFF:
        res.append({"path":path,"err":ctypes.get_last_error()}); continue
    b=(ctypes.c_ubyte*8192)(); got=wintypes.DWORD(0)
    ok=k32.DeviceIoControl(h,0x000B0192,None,0,b,8192,ctypes.byref(got),None)
    desc=bytes(b[:got.value]) if ok else None
    caps={}; pp=ctypes.c_void_p()
    if hid.HidD_GetPreparsedData(h,ctypes.byref(pp)) and pp.value:
        c=HIDP_CAPS(); hid.HidP_GetCaps(pp,ctypes.byref(c))
        caps=dict(Usage=hex(c.Usage),UsagePage=hex(c.UsagePage),In=c.InputReportByteLength,
                  Out=c.OutputReportByteLength,Feat=c.FeatureReportByteLength,LinkColl=c.NumberLinkCollectionNodes,
                  InBtn=c.NumberInputButtonCaps,InVal=c.NumberInputValueCaps,
                  OutBtn=c.NumberOutputButtonCaps,OutVal=c.NumberOutputValueCaps,
                  FeatBtn=c.NumberFeatureButtonCaps,FeatVal=c.NumberFeatureValueCaps)
    k32.CloseHandle.argtypes=[ctypes.c_void_p]; k32.CloseHandle(h)
    res.append({"path":path,"desc":desc.hex() if desc else None,"len":len(desc) if desc else 0,"caps":caps})
setupapi.SetupDiDestroyDeviceInfoList(hdev)
json.dump(res,open("hid_devices.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("GXTP5100 HID 接口数 = %d\n"%len(res))
for r in res:
    print("="*76); print(r["path"])
    if "err" in r: print("   err=%d"%r["err"]); continue
    print("   descriptor = %d 字节   caps = %s"%(r["len"],r["caps"]))
    if r["desc"]:
        d=bytes.fromhex(r["desc"]); open("col_%s.bin"%r["path"].split("#")[-1][:8],"wb").write(d)
        for k in range(0,len(d),16):
            print("     %04X  %s"%(k," ".join("%02X"%c for c in d[k:k+16])))
