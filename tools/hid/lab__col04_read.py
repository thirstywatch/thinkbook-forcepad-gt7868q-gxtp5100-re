#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""col04_read.py -- 用 Col04 class 0x20（_I2C_DIRECT_RW）读 GT7868Q 的地址空间

帧（Gx.cs 实测可用，16 位地址）：
    读: [0E 20 00 00 05 01 addrH addrL lenH lenL]
    响应: [0E 20 <cont> <seq> <len> <data...>]   cont=1 表示还有续块
取回方式：HidD_GetInputReport —— 项目记录里这是有效的读通道（不是 GetFeature）

用法：
    python col04_read.py 0x96F8 32
    python col04_read.py 0x96F8 32 64      # 指定缓冲长度（试 64 / 65）
"""
import ctypes
import sys
import time
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
COL04_PATH = ("\\\\?\\HID#GXTP5100&Col04#5&52a7aed&0&0003#"
              "{4d1e55b2-f16f-11cf-88cb-001111000030}")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
hid.HidD_SetOutputReport.restype = wintypes.BOOLEAN
hid.HidD_SetOutputReport.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG]
hid.HidD_GetInputReport.restype = wintypes.BOOLEAN
hid.HidD_GetInputReport.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG]
# 也试 ReadFile 路径（项目记录：持续取报文必须用 ReadFile）
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.DWORD,
                              ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]


def main():
    addr = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x96F8
    size = int(sys.argv[2], 0) if len(sys.argv) > 2 else 32
    bufs = [int(x) for x in sys.argv[3:]] or [65, 64, 10, 8]

    h = kernel32.CreateFileW(COL04_PATH, GENERIC_READ | GENERIC_WRITE,
                             FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                             OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE_VALUE or h is None:
        print("CreateFile FAILED err =", ctypes.get_last_error())
        return 1

    pkt = bytearray(65)
    pkt[0] = 0x0E
    pkt[1] = 0x20
    pkt[4] = 0x05
    pkt[5] = 0x01
    pkt[6] = (addr >> 8) & 0xFF
    pkt[7] = addr & 0xFF
    pkt[8] = (size >> 8) & 0xFF
    pkt[9] = size & 0xFF
    buf = ctypes.create_string_buffer(bytes(pkt), 65)
    ok = hid.HidD_SetOutputReport(h, ctypes.cast(buf, ctypes.c_char_p), 65)
    print(f"read addr={addr:#06x} size={size}  send={bool(ok)} err={ctypes.get_last_error()}")
    time.sleep(0.15)

    for n in bufs:
        r = ctypes.create_string_buffer(max(n, 1))
        okr = hid.HidD_GetInputReport(h, ctypes.cast(r, ctypes.c_char_p), n)
        e1 = ctypes.get_last_error()
        got = bytes(r.raw[:min(n, 24)])
        print(f"  GetInputReport(len={n:3d}) ok={bool(okr)} err={e1:3d}  data={got.hex(' ').upper()}")

    # ReadFile 路径
    n = 65
    r2 = ctypes.create_string_buffer(n)
    read = wintypes.DWORD(0)
    okf = kernel32.ReadFile(h, ctypes.cast(r2, ctypes.c_char_p), n, ctypes.byref(read), None)
    print(f"  ReadFile(65)      ok={bool(okf)} err={ctypes.get_last_error():3d} n={read.value}  "
          f"data={bytes(r2.raw[:min(read.value,24)]).hex(' ').upper()}")

    kernel32.CloseHandle(h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
