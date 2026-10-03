"""EC 窗口噪声基线：连拍 3 张快照（间隔 2 秒），报告变化字节。
只读物理内存 0xFE0B0400，无任何写操作。"""
import ctypes, time, collections
from ctypes import wintypes
IOCTL_READ_PHYS=0x222808
class PhysRw(ctypes.Structure):
    _fields_=[("physicalAddress",ctypes.c_ulonglong),("size",ctypes.c_uint32),
              ("access",ctypes.c_uint32),("buffer",ctypes.c_ulonglong)]
k32=ctypes.WinDLL("kernel32",use_last_error=True)
k32.CreateFileW.restype=ctypes.c_void_p
k32.CreateFileW.argtypes=[ctypes.c_wchar_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
k32.DeviceIoControl.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_ptr if hasattr(wintypes,'void_ptr') else ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
k32.DeviceIoControl.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
h=k32.CreateFileW("\\\\.\\RwDrv",0xC0000000,0,None,3,0x80,None)
if not h or h==0xFFFFFFFFFFFFFFFF: print("RwDrv 打不开"); raise SystemExit
def rd(a,n):
    b=(ctypes.c_ubyte*n)(); r=PhysRw(a,n,0,ctypes.cast(b,ctypes.c_void_p).value); g=wintypes.DWORD(0)
    ok=k32.DeviceIoControl(h,IOCTL_READ_PHYS,ctypes.byref(r),ctypes.sizeof(r),None,0,ctypes.byref(g),None)
    return bytes(b) if ok else None
BASE=0xFE0B0400; N=0x300
snaps=[]
for i in range(3):
    d=rd(BASE,N)
    if d is None: print("读失败 @ %d"%i); raise SystemExit
    snaps.append(d)
    if i<2: time.sleep(2.0)
print("3 张快照拍摄完成（间隔 2 秒）\n")

# 稳定字节 vs 变化字节
stable=[]; changed=collections.defaultdict(list)
for off in range(N):
    vals=[s[off] for s in snaps]
    if len(set(vals))==1:
        stable.append(off)
    else:
        changed[off]=vals

print("=== 稳定字节: %d / %d (%.0f%%) ==="%(len(stable),N,100*len(stable)/N))
print("=== 变化字节: %d 个 ==="%len(changed))
print("\n%-8s %-30s %-12s %s"%("偏移","值(3次)","变化?","备注"))
for off in sorted(changed):
    vals=changed[off]
    note=""
    if 0x12<=off<=0x17: note="温度传感器区"
    elif off==0x0B8: note="★ LIDF 所在字节！"
    elif 0x222<=off<=0x230: note="EC 命令块"
    elif off in (0x220,0x221): note="签名 5A A5"
    print("  0x%03X   %-30s %s   %s"%(off," ".join("%02X"%v for v in vals),
          "↔" if len(set(vals))>1 else " ",note))

# 相邻稳定区的边界
print("\n=== 变化字节的空间分布 ===")
if changed:
    offs=sorted(changed)
    runs=[[offs[0],offs[0]]]
    for o in offs[1:]:
        if o==runs[-1][1]+1: runs[-1][1]=o
        else: runs.append([o,o])
    for a,b in runs:
        print("   0x%03X..0x%03X (%d 字节)"%(a,b,b-a+1))

# LIDF 专项
print("\n=== LIDF 专项（字节 0x0B8 位 1）===")
for i,s in enumerate(snaps):
    v=s[0x0B8]
    print("   快照%d: 0x0B8 = 0x%02X = 0b%s   LIDF(bit1) = %d"%(i+1,v,format(v,'08b'),(v>>1)&1))
print("   （当前盖子是【开】）")

# 温度区
print("\n=== 温度区（0x12-0x17）===")
for i,s in enumerate(snaps):
    print("   快照%d: %s °C"%(i+1," ".join(str(s[o]) for o in range(0x12,0x18))))
k32.CloseHandle(h)
