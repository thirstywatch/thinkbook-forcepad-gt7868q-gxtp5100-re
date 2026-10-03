import ctypes, json, re
from ctypes import wintypes
k32=ctypes.WinDLL("kernel32",use_last_error=True); hid=ctypes.WinDLL("hid",use_last_error=True)
k32.CreateFileW.restype=ctypes.c_void_p
k32.CreateFileW.argtypes=[ctypes.c_wchar_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
for f in (hid.HidD_GetFeature,hid.HidD_GetProductString):
    f.argtypes=[ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD]
hid.HidD_GetFeature.restype=wintypes.BOOL
D={}
for r in json.load(open("hid_devices.json",encoding="utf-8")):
    m=re.search(r"(col\d\d)", r["path"], re.I)
    if m: D[m.group(1).lower()]=r
print("collections:", sorted(D))
print("\n=== 各 collection 权限（能力检查，不写） ===")
for k in sorted(D):
    caps=D[k]["caps"]; parts=[]
    for acc,nm in ((0x80000000,"只读"),(0xC0000000,"读写")):
        ctypes.set_last_error(0)
        h=k32.CreateFileW(D[k]["path"],acc,3,None,3,0,None)
        if h and h!=0xFFFFFFFFFFFFFFFF:
            parts.append(nm+"=OK"); k32.CloseHandle(h)
        else:
            parts.append(nm+"=FAIL(err=%d)"%ctypes.get_last_error())
    print("   %-6s In=%-3s Out=%-3s Feat=%-4s  %s"%(k,caps.get("In"),caps.get("Out"),caps.get("Feat"),"  ".join(parts)))

print("\n=== Col03 feature 只读尝试（Feat=3） ===")
h=k32.CreateFileW(D["col03"]["path"],0x80000000,3,None,3,0,None)
if h and h!=0xFFFFFFFFFFFFFFFF:
    for rid in range(0,8):
        buf=(ctypes.c_ubyte*8)(); buf[0]=rid
        ctypes.set_last_error(0); ok=hid.HidD_GetFeature(h,buf,8)
        print("   RID=%d ok=%-5s err=%-3d -> %s"%(rid,bool(ok),ctypes.get_last_error(),
              " ".join("%02X"%c for c in buf) if ok else "-"))
    k32.CloseHandle(h)
else: print("   打开失败 err=%d"%ctypes.get_last_error())

print("\n=== Col04 厂商通道 ===")
h=k32.CreateFileW(D["col04"]["path"],0xC0000000,3,None,3,0,None)
if h and h!=0xFFFFFFFFFFFFFFFF:
    b=ctypes.create_unicode_buffer(128)
    if hid.HidD_GetProductString(h,b,256): print("   Product = %r"%b.value)
    k32.CloseHandle(h)
    print("   ✔ 读写均可打开 → 通道空闲，用户态可直接使用")
