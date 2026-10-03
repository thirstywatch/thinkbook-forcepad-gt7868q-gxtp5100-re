#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""col04_sweep.py -- 小心地探测 Col04 的【未测 class】

依据《触控板结论总表》：
  · 已实现（能应答）= 分段集合 `0x00–0x0D` + `0x10–0x13` + `0x20`（≥19 个），**不是连续区间**
  · **未测** = `0x30–0x7F` / `0x80` / `0xA0` / `0xA1`
  · **已实现但语义未定** = `0x10–0x13`（其中 `0x12` 已知 = 官方 flash 写命令 `0e 12`）

⚠️ 红线（项目 §9.3）：**不能大规模扫描** —— 累积流量会拖垮通道
   （日志证据：`0x30` 尚未发送前，连已知有效的 readMem 就已 err=122）
   ⇒ 本脚本：**每帧间隔 ≥1.5 s、总量 ≤30 帧、每组之间额外休息**。

判据（纪律 84）：**"能发"不算数，要看副作用** —— 触控板是否震动 / 指针是否异常。

用法：
    python col04_sweep.py phase1     # class 0x10-0x13, 0x30-0x3F @ sub=0
    python col04_sweep.py phase2     # class 0x80, 0xA0(部分), 0xA1(部分)
    python col04_sweep.py custom 0xA0 0x0E00
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
                                 ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.c_void_p]
hid.HidD_SetOutputReport.restype = wintypes.BOOLEAN
hid.HidD_SetOutputReport.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG]
hid.HidD_GetInputReport.restype = wintypes.BOOLEAN
hid.HidD_GetInputReport.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG]

PLANS = {
    # 已实现但语义未定（最值得打）
    "phase1": [(c, 0x0000) for c in (0x10, 0x11, 0x12, 0x13)]
              + [(c, 0x0000) for c in range(0x30, 0x38)],
    # 未测的高位 class（0x80 被标为"疑似写入族"，放最后、少打）
    "phase2": [(0x80, 0x0000), (0x80, 0x0100),
               (0xA0, 0x0E00), (0xA0, 0x1000), (0xA0, 0x1300), (0xA0, 0x1500),
               (0xA1, 0x0300), (0xA1, 0x0600)],
}


def send(h, cls, sub, payload=b""):
    pkt = bytearray(65)
    pkt[0] = 0x0E
    pkt[1] = cls & 0xFF
    pkt[2] = sub & 0xFF
    pkt[3] = (sub >> 8) & 0xFF
    pkt[4] = (len(payload) + 7) & 0xFF
    pkt[5] = 0x00
    for i, b in enumerate(payload):
        pkt[6 + i] = b
    buf = ctypes.create_string_buffer(bytes(pkt), 65)
    ok = hid.HidD_SetOutputReport(h, ctypes.cast(buf, ctypes.c_char_p), 65)
    return bool(ok), ctypes.get_last_error()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "phase1"
    if mode == "custom":
        plan = [(int(sys.argv[2], 0), int(sys.argv[3], 0))]
        gap = 1500
    elif mode == "range":
        lo = int(sys.argv[2], 0)
        hi = int(sys.argv[3], 0)
        sub = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
        gap = int(sys.argv[5]) if len(sys.argv) > 5 else 1000
        plan = [(c, sub) for c in range(lo, hi + 1)]
    else:
        plan = PLANS.get(mode, PLANS["phase1"])
        gap = 1500

    h = kernel32.CreateFileW(COL04_PATH, GENERIC_READ | GENERIC_WRITE,
                             FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                             OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE_VALUE or h is None:
        print("CreateFile FAILED err =", ctypes.get_last_error())
        return 1

    print(f"=== {mode} : {len(plan)} frames, gap {gap} ms ===")
    print("★ 请把手放在触控板上，注意有没有【震动】或指针异常")
    for i, (c, s) in enumerate(plan, 1):
        ok, err = send(h, c, s)
        ts = time.strftime('%H:%M:%S')
        print(f"  [{i:2d}/{len(plan)}] class={c:#04x} sub={s:#06x}  send={ok} err={err}  {ts}")
        time.sleep(gap / 1000.0)
    print("done. 如果全程无震动 → 这些 class 也与触觉无关")
    kernel32.CloseHandle(h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
