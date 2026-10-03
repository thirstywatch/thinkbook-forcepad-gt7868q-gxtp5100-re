import ctypes, sys
from ctypes import wintypes
GENERIC_READ=0x80000000; GENERIC_WRITE=0x40000000
FILE_SHARE_READ=1; FILE_SHARE_WRITE=2; OPEN_EXISTING=3
INVALID=ctypes.c_void_p(-1).value
k32=ctypes.WinDLL('kernel32',use_last_error=True); hd=ctypes.WinDLL('hid',use_last_error=True)
class HIDP_CAPS(ctypes.Structure):
    _fields_=[('Usage',wintypes.USHORT),('UsagePage',wintypes.USHORT),
              ('InputReportByteLength',wintypes.USHORT),('OutputReportByteLength',wintypes.USHORT),
              ('FeatureReportByteLength',wintypes.USHORT),('Reserved',wintypes.USHORT*17),
              ('NumberLinkCollectionNodes',wintypes.USHORT),('NumberInputButtonCaps',wintypes.USHORT),
              ('NumberInputValueCaps',wintypes.USHORT),('NumberInputDataIndices',wintypes.USHORT),
              ('NumberOutputButtonCaps',wintypes.USHORT),('NumberOutputValueCaps',wintypes.USHORT),
              ('NumberOutputDataIndices',wintypes.USHORT),('NumberFeatureButtonCaps',wintypes.USHORT),
              ('NumberFeatureValueCaps',wintypes.USHORT),('NumberFeatureDataIndices',wintypes.USHORT)]
k32.CreateFileW.restype=wintypes.HANDLE
k32.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
hd.HidD_GetPreparsedData.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_void_p)]
hd.HidP_GetCaps.argtypes=[ctypes.c_void_p,ctypes.POINTER(HIDP_CAPS)]
GUID='{4d1e55b2-f16f-11cf-88cb-001111000030}'
for col in ('Col01','Col02','Col03','Col04'):
    p=("\\\\?\\HID#GXTP5100&%s#5&52a7aed&0&%s#"%(
        col, {'Col01':'0000','Col02':'0001','Col03':'0002','Col04':'0003'}[col]))+GUID
    h=k32.CreateFileW(p,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,None,OPEN_EXISTING,0,None)
    if not h or h==INVALID:
        print(f"{col}: CreateFile err={ctypes.get_last_error()}"); continue
    pp=ctypes.c_void_p()
    if not hd.HidD_GetPreparsedData(h,ctypes.byref(pp)):
        print(f"{col}: GetPreparsedData err={ctypes.get_last_error()}"); continue
    c=HIDP_CAPS()
    ok=hd.HidP_GetCaps(pp,ctypes.byref(c))
    print(f"{col}: ok={bool(ok)} UP={c.UsagePage:#06x} U={c.Usage:#06x} "
          f"InLen={c.InputReportByteLength} OutLen={c.OutputReportByteLength} FeatLen={c.FeatureReportByteLength} "
          f"nInVC={c.NumberInputValueCaps} nOutVC={c.NumberOutputValueCaps} nFeatVC={c.NumberFeatureValueCaps}")
    k32.CloseHandle(h)
