"""EC 窗口 LIDF 验证实验。
用法：python ec_lid_verify.py
流程：开盖基线 → 提示合盖 → 快照B → 提示开盖 → 快照C → 三方比对
只读，无任何写操作。噪声字节自动过滤。"""
import ctypes, time, sys, collections
from ctypes import wintypes
IOCTL_READ_PHYS=0x222808
class PhysRw(ctypes.Structure):
    _fields_=[("physicalAddress",ctypes.c_ulonglong),("size",ctypes.c_uint32),
              ("access",ctypes.c_uint32),("buffer",ctypes.c_ulonglong)]
k32=ctypes.WinDLL("kernel32",use_last_error=True)
k32.CreateFileW.restype=ctypes.c_void_p
k32.CreateFileW.argtypes=[ctypes.c_wchar_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
k32.DeviceIoControl.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
h=k32.CreateFileW("\\\\.\\RwDrv",0xC0000000,0,None,3,0x80,None)
if not h or h==0xFFFFFFFFFFFFFFFF: print("RwDrv 打不开"); sys.exit(1)
def rd(a,n):
    b=(ctypes.c_ubyte*n)(); r=PhysRw(a,n,0,ctypes.cast(b,ctypes.c_void_p).value); g=wintypes.DWORD(0)
    ok=k32.DeviceIoControl(h,IOCTL_READ_PHYS,ctypes.byref(r),ctypes.sizeof(r),None,0,ctypes.byref(g),None)
    return bytes(b) if ok else None
BASE=0xFE0B0400; N=0x300
NOISE={0x012,0x017,0x0A7,0x0B0,0x0B1,0x0C6,0x0DB,0x0E9,0x0F8,0x0F9,0x103,0x105,0x12A,0x12C}

def snap(label):
    print("\n[%s] 按回车拍摄..."%label); input()
    d=rd(BASE,N)
    if d is None: print("  读失败！"); sys.exit(1)
    print("  已拍摄 (%d 字节)"%len(d))
    return d

def diff(a,b,na,nb):
    ch=[(i,a[i],b[i]) for i in range(N) if a[i]!=b[i]]
    sig=[x for x in ch if x[0] not in NOISE]
    noi=[x for x in ch if x[0] in NOISE]
    return ch,sig,noi

print("="*70)
print("EC 窗口 LIDF 验证实验")
print("="*70)

A=snap("A: 当前盖子是【开】的基线")

B=snap("B: 请把盖子【合上】，等 2 秒后按回车")

time.sleep(0.5)
C=snap("C: 请把盖子【重新打开】，等 2 秒后按回车")

print("\n" + "="*70)
print("=== 比对 A(开) vs B(合) ===")
ch,sig,noi=diff(A,B,"A(开)","B(合)")
print("  变化字节 %d 个（信号 %d + 噪声 %d）"%(len(ch),len(sig),len(noi)))
for off,va,vb in sig:
    note = " ★ LIDF！" if off==0x0B8 else (" EC 命令块" if 0x222<=off<=0x230 else "")
    print("    0x%03X: 0x%02X → 0x%02X  (bit 翻转: %s)%s"%(off,va,vb,
          [j for j in range(8) if (va^vb)>>j&1],note))

print("\n=== 比对 B(合) vs C(开) ===")
ch2,sig2,noi2=diff(B,C,"B(合)","C(开)")
print("  变化字节 %d 个（信号 %d + 噪声 %d）"%(len(ch2),len(sig2),len(noi2)))
for off,va,vb in sig2:
    note = " ★ LIDF！" if off==0x0B8 else (" EC 命令块" if 0x222<=off<=0x230 else "")
    print("    0x%03X: 0x%02X → 0x%02X  (bit 翻转: %s)%s"%(off,va,vb,
          [j for j in range(8) if (va^vb)>>j&1],note))

print("\n=== 比对 A(开) vs C(开)（应回到基线）===")
ch3,sig3,noi3=diff(A,C,"A(开)","C(开)")
print("  变化字节 %d 个（信号 %d + 噪声 %d）"%(len(ch3),len(sig3),len(noi3)))
for off,va,vb in sig3:
    note = " ★ LIDF！" if off==0x0B8 else ""
    print("    0x%03X: 0x%02X → 0x%02X%s"%(off,va,vb,note))

print("\n=== LIDF 结论 ===")
for nm,s in (("A(开)",A),("B(合)",B),("C(开)",C)):
    v=s[0x0B8]
    print("  %s: 0x0B8 = 0x%02X = 0b%s   bit1(LIDF) = %d"%(nm,v,format(v,'08b'),(v>>1)&1))
lidf_a=(A[0x0B8]>>1)&1; lidf_b=(B[0x0B8]>>1)&1; lidf_c=(C[0x0B8]>>1)&1
if lidf_a!=lidf_b and lidf_b!=lidf_c and lidf_a==lidf_c:
    print("\n  ★★★ LIDF 确认！开=%d 合=%d 开=%d —— 完美的 A/B/A 模式"%(lidf_a,lidf_b,lidf_c))
elif 0x0B8 in [x[0] for x in sig]:
    print("\n  ★ 0x0B8 有变化但模式不完全 A/B/A —— 检查上下文")
else:
    print("\n  ✘ 0x0B8 未变化 —— LIDF 可能不在这个偏移，或需重新解析")

# 如果有其他稳定变化的信号字节，也报告
all_sig_offs = set(x[0] for x in sig) | set(x[0] for x in sig2)
stable_sig = all_sig_offs - {0x0B8} - NOISE
if stable_sig:
    print("\n=== 其他随开合变化的字节（排除噪声与 LIDF）===")
    for off in sorted(stable_sig):
        print("    0x%03X: A=0x%02X B=0x%02X C=0x%02X"%(off,A[off],B[off],C[off]))
k32.CloseHandle(h)
