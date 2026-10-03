"""只读探测：Col03 的 feature report；并做 Col04 写权限「能力检查」（不实际写）。"""
import ctypes, json
from ctypes import wintypes
k32=ctypes.WinDLL("kernel32",use_last_error=True); hid=ctypes.WinDLL("hid",use_last_error=True)
k32.CreateFileW.restype=ctypes.c_void_p
k32.CreateFileW.argtypes=[ctypes.c_wchar_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
hid.HidD_GetFeature.argtypes=[ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD]
hid.HidD_GetFeature.restype=wintypes.BOOL
hid.HidD_GetInputReport.argtypes=[ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD]
hid.HidD_GetProductString.argtypes=[ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD]
GENERIC_READ=0x80000000; GENERIC_WRITE=0x40000000; SHARE=3; OPEN_EXISTING=3
dev={r["path"].split('#')[1][:11]:r["path"] for r in json.load(open("hid_devices.json",encoding="utf-8"))}

print("=== 1) 各 collection 打开权限（能力检查，不做任何写） ===")
for k in sorted(dev):
    p=dev[k]
    row=[]
    for acc,nm in ((GENERIC_READ,"只读"),(GENERIC_READ|GENERIC_WRITE,"读写")):
        ctypes.set_last_error(0)
        h=k32.CreateFileW(p,acc,SHARE,None,OPEN_EXISTING,0,None)
        ok = bool(h) and h!=0xFFFFFFFFFFFFFFFF
        row.append("%s=%s%s"%(nm,"✔" if ok else "✘", "" if ok else "(err=%d)"%ctypes.get_last_error()))
        if ok: k32.CloseHandle(h)
    print("   %-20s %s"%(k,"  ".join(row)))

print("\n=== 2) Col03 feature report 读取（只读，单次） ===")
h=k32.CreateFileW(dev["gxtp5100&co"],GENERIC_READ,SHARE,None,OPEN_EXISTING,0,None)
if h and h!=0xFFFFFFFFFFFFFFFF:
    for rid in (0,1,2,3,4,5):
        buf=(ctypes.c_ubyte*64)(); buf[0]=rid
        ctypes.set_last_error(0)
        ok=hid.HidD_GetFeature(h,buf,64)
        print("   RID=%d  ok=%s err=%d  ->  %s"%(rid,bool(ok),ctypes.get_last_error(),
              " ".join("%02X"%c for c in buf[:8]) if ok else "-"))
    k32.CloseHandle(h)
else:
    print("   Col03 打开失败 err=%d"%ctypes.get_last_error())

print("\n=== 3) Col04（厂商通道）信息 ===")
h=k32.CreateFileW(dev["gxtp5100&co"],GENERIC_READ|GENERIC_WRITE,SHARE,None,OPEN_EXISTING,0,None)
print("   读写打开: %s"%("成功 ✔（说明我们能用这条通道）" if h and h!=0xFFFFFFFFFFFFFFFF else "失败 err=%d"%ctypes.get_last_error()))
if h and h!=0xFFFFFFFFFFFFFFFF:
    buf=ctypes.create_unicode_buffer(128)
    if hid.HidD_GetProductString(h,buf,256): print("   ProductString = %r"%buf.value)
    vs=ctypes.create_unicode_buffer(128)
    if hid.HidD_GetManufacturerString(h,vs,256): print("   Manufacturer  = %r"%vs.value)
    ss=ctypes.create_unicode_buffer(128)
    if hid.HidD_GetSerialNumberString(h,ss,256): print("   SerialNumber  = %r"%ss.value)
    k32.CloseHandle(h)
