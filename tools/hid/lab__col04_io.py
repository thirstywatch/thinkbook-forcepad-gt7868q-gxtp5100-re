# -*- coding: utf-8 -*-
"""col04_io.py -- Col04 读写的正确姿势（重叠 I/O + 超时）

关键事实（本次实测）：
  Col04 = HID 集合 UP=0xFF00/U=0x01, InputReportByteLength=65, OutputReportByteLength=65
  · 发送：HidD_SetOutputReport(h, buf65, 65)     —— buf[0] = 0x0E (RID)
  · 取回：**HidD_GetInputReport 在本机恒 err=87**（设备未实现该 IOCTL）
          ⇒ 必须用 **ReadFile（异步输入报文）+ 超时**，且句柄要以 FILE_FLAG_OVERLAPPED 打开
          （裸 ReadFile 会永久阻塞 —— 之前那次 SIGTERM 就是它）

用法: python col04_io.py read 0x96F8 32 [timeout_ms]
"""
import ctypes, sys, time
from ctypes import wintypes

GENERIC_READ=0x80000000; GENERIC_WRITE=0x40000000
FILE_SHARE_READ=1; FILE_SHARE_WRITE=2; OPEN_EXISTING=3
FILE_FLAG_OVERLAPPED=0x40000000
INVALID=ctypes.c_void_p(-1).value
WAIT_OBJECT_0=0

k32=ctypes.WinDLL('kernel32',use_last_error=True)
hd=ctypes.WinDLL('hid',use_last_error=True)

class OVERLAPPED(ctypes.Structure):
    _fields_=[('Internal',ctypes.POINTER(ctypes.c_ulong)),('InternalHigh',ctypes.POINTER(ctypes.c_ulong)),
              ('Offset',wintypes.DWORD),('OffsetHigh',wintypes.DWORD),('hEvent',wintypes.HANDLE)]

k32.CreateFileW.restype=wintypes.HANDLE
k32.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
k32.CreateEventW.restype=wintypes.HANDLE
k32.ReadFile.argtypes=[wintypes.HANDLE,ctypes.c_char_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.POINTER(OVERLAPPED)]
k32.GetOverlappedResult.argtypes=[wintypes.HANDLE,ctypes.POINTER(OVERLAPPED),ctypes.POINTER(wintypes.DWORD),wintypes.BOOL]
hd.HidD_SetOutputReport.argtypes=[wintypes.HANDLE,ctypes.c_char_p,wintypes.ULONG]

COL04=("\\\\?\\HID#GXTP5100&Col04#5&52a7aed&0&0003#{4d1e55b2-f16f-11cf-88cb-001111000030}")

def open_dev():
    h=k32.CreateFileW(COL04,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,None,
                      OPEN_EXISTING,FILE_FLAG_OVERLAPPED,None)
    if not h or h==INVALID:
        print("CreateFile err=",ctypes.get_last_error()); return None
    return h

def send_raw(h,pkt):
    pkt=bytearray(pkt); pkt += bytes(65-len(pkt))
    buf=ctypes.create_string_buffer(bytes(pkt[:65]),65)
    return bool(hd.HidD_SetOutputReport(h,ctypes.cast(buf,ctypes.c_char_p),65)), ctypes.get_last_error()

def send(h,cls,sub,payload=b""):
    """通用(写)帧: pkt[4]=len+7, pkt[5]=0"""
    pkt=bytearray(65); pkt[0]=0x0E; pkt[1]=cls&0xFF
    pkt[2]=sub&0xFF; pkt[3]=(sub>>8)&0xFF
    pkt[4]=(len(payload)+7)&0xFF; pkt[5]=0
    for i,b in enumerate(payload): pkt[6+i]=b
    return send_raw(h,pkt)

def send_read(h,addr16,size):
    """★ class 0x20 读帧（照抄 Gx.cs）: pkt[4]=0x05, pkt[5]=0x01"""
    pkt=bytearray(10)
    pkt[0]=0x0E; pkt[1]=0x20; pkt[4]=0x05; pkt[5]=0x01
    pkt[6]=(addr16>>8)&0xFF; pkt[7]=addr16&0xFF
    pkt[8]=(size>>8)&0xFF;   pkt[9]=size&0xFF
    return send_raw(h,pkt)

def recv(h,timeout_ms=800):
    buf=ctypes.create_string_buffer(65)
    ev=k32.CreateEventW(None,True,False,None)
    ov=OVERLAPPED(); ov.hEvent=ev
    n=wintypes.DWORD(0)
    r=k32.ReadFile(h,buf,65,ctypes.byref(n),ctypes.byref(ov))
    err=ctypes.get_last_error()
    if not r and err!=997:      # 997 = ERROR_IO_PENDING
        k32.CloseHandle(ev); return None,f"ReadFile fail err={err}"
    w=k32.WaitForSingleObject(ev,timeout_ms)
    if w!=WAIT_OBJECT_0:
        k32.CancelIo(h); k32.CloseHandle(ev)
        return None,f"timeout({timeout_ms}ms)"
    got=wintypes.DWORD(0)
    k32.GetOverlappedResult(h,ctypes.byref(ov),ctypes.byref(got),False)
    k32.CloseHandle(ev)
    return bytes(buf.raw[:got.value]),None

def main():
    mode=sys.argv[1] if len(sys.argv)>1 else "read"
    addr=int(sys.argv[2],0) if len(sys.argv)>2 else 0x96F8
    size=int(sys.argv[3],0) if len(sys.argv)>3 else 32
    to=int(sys.argv[4]) if len(sys.argv)>4 else 800
    h=open_dev()
    if not h: return 1
    ok,err=send_read(h,addr,size)
    print(f"send read-frame addr={addr:#06x} size={size} -> {ok} err={err}")
    time.sleep(0.12)
    acc=b""
    for i in range(12):
        d,why=recv(h,to)
        if d is None:
            print(f"  recv[{i}] -> {why}"); break
        cont=d[2] if len(d)>2 else None
        ln=d[4] if len(d)>4 else 0
        print(f"  recv[{i}] len={ln} cont={cont}  {d[:16].hex(' ').upper()}")
        if ln<=60: acc+=d[5:5+ln]
        else: acc+=d[5:65]
        if cont==0: break
    print("ACC:",acc[:64].hex(' ').upper())
    print("ASCII:",''.join(chr(b) if 32<=b<127 else '.' for b in acc[:64]))
    k32.CloseHandle(h)
    return 0

if __name__=="__main__":
    sys.exit(main())
