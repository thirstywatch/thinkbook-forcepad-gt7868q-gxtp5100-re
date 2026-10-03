#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""col04_send.py -- 向触控板的 Col04（厂商定义）集合发 HID 输出报文

背景（《全书》§9.2.8 定案的真机帧结构）：
    pkt[0] = 0x0E          HID report ID
    pkt[1] = class         0xA0 / 0xA1 / 0xA2
    pkt[2] = subcmd 低字节
    pkt[3] = subcmd 高字节
    pkt[4] = 长度           写 = len+7 ；读样例里是 5
    pkt[5] = 方向           写 = 0 ；读 = 1
    pkt[6..] = payload

本次目的：发 class=0xA0 / subcmd=0x0D00（项目已知【唯一能启动 TF100A 检测引擎】的主机入口），
然后用 RWE 立刻探 I²C0 的 0x5A —— 检验"GT7868Q 是否会被唤起给 AW86927 上电"。

设备路径取自项目自己的 GoodixCmd.cs（Col03 那条同族）：
    \\?\HID#GXTP5100&Col04#5&52a7aed&0&0003#{4d1e55b2-f16f-11cf-88cb-001111000030}

用法：
    python col04_send.py 0xA0 0x0D00 [次数] [间隔ms]
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

HID_GUID = "{4d1e55b2-f16f-11cf-88cb-001111000030}"
COL04_PATH = ("\\\\?\\HID#GXTP5100&Col04#5&52a7aed&0&0003#" + HID_GUID)

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)

kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.c_void_p]
hid.HidD_SetOutputReport.restype = wintypes.BOOLEAN
hid.HidD_SetOutputReport.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG]
hid.HidD_GetInputReport.restype = wintypes.BOOLEAN
hid.HidD_GetInputReport.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG]


def build_pkt(cls, sub, payload=b""):
    pkt = bytearray(65)          # RID + 64
    pkt[0] = 0x0E
    pkt[1] = cls & 0xFF
    pkt[2] = sub & 0xFF
    pkt[3] = (sub >> 8) & 0xFF
    pkt[4] = (len(payload) + 7) & 0xFF   # 写 = len+7
    pkt[5] = 0x00                        # 方向：写
    for i, b in enumerate(payload):
        pkt[6 + i] = b
    return bytes(pkt)


def main():
    cls = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0xA0
    sub = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x0D00
    times = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    gap = int(sys.argv[4]) if len(sys.argv) > 4 else 500

    print(f"path = {COL04_PATH}")
    h = kernel32.CreateFileW(COL04_PATH, GENERIC_READ | GENERIC_WRITE,
                             FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                             OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE_VALUE or h is None:
        print("CreateFile FAILED err =", ctypes.get_last_error())
        return 1

    pkt = build_pkt(cls, sub)
    print(f"frame = {pkt[:8].hex(' ').upper()}  (class={cls:#x} sub={sub:#04x})")

    ok_cnt = 0
    for k in range(times):
        buf = ctypes.create_string_buffer(pkt, len(pkt))
        ok = hid.HidD_SetOutputReport(h, ctypes.cast(buf, ctypes.c_char_p), 65)
        err = ctypes.get_last_error()
        if ok:
            ok_cnt += 1
        print(f"  [{k+1}/{times}] send={'True' if ok else 'False'} err={err}  t={time.strftime('%H:%M:%S')}")
        if k != times - 1:
            time.sleep(gap / 1000.0)

    # 顺手试一次读，看设备有没有回
    r = ctypes.create_string_buffer(65)
    okr = hid.HidD_GetInputReport(h, ctypes.cast(r, ctypes.c_char_p), 65)
    print(f"read-1st-byte ok={bool(okr)} data={bytes(r.raw[:12]).hex(' ').upper()} err={ctypes.get_last_error()}")

    kernel32.CloseHandle(h)
    print(f"done. ok={ok_cnt}/{times}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
