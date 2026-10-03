#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND65 - 诊断: 搞清 Windows I2C-HID 上 GET/SET_FEATURE 到底通不通
只做探测, 不改任何状态。
"""
import hid
import sys
import time

COL04 = b'\\\\?\\HID#GXTP5100&Col04#5&52a7aed&0&0003#{4d1e55b2-f16f-11cf-88cb-001111000030}'


def show(tag, b):
    if b is None:
        print(f"  {tag}: <None>")
        return
    print(f"  {tag}: len={len(b)}  {b[:24].hex(' ').upper()}")


def main():
    print("=" * 82)
    print("ROUND65 Windows I2C-HID Feature-Report 通路诊断")
    print("=" * 82)

    h = hid.device()
    try:
        h.open_path(COL04)
    except Exception as e:
        print(f"打开失败: {e}")
        return 1
    print("打开 COL04 成功\n")

    # --- A. 先试试直接 GET_FEATURE(0x0e) 看设备初始状态 ---
    print("[A] GET_FEATURE(report_id=0x0e) 原始尝试, 各种长度")
    for sz in (65, 64, 10, 8):
        try:
            r = h.get_feature_report(0x0E, sz)
            show(f"len={sz}", r)
        except Exception as e:
            print(f"  len={sz}: 异常 {type(e).__name__}: {e}")
    print()

    # --- B. 试试 GET_FEATURE(0)  (Windows 有些设备 report id=0) ---
    print("[B] GET_FEATURE(report_id=0x00)")
    for sz in (65, 64):
        try:
            r = h.get_feature_report(0x00, sz)
            show(f"len={sz}", r)
        except Exception as e:
            print(f"  len={sz}: 异常 {type(e).__name__}: {e}")
    print()

    # --- C. 发一个最小 SET_FEATURE, 然后立刻 GET 看回什么 ---
    print("[C] SET_FEATURE: [0e 20 00 00 05 01 96 F8 00 03] + 零填充到 65")
    buf = bytearray(65)
    buf[0] = 0x0E
    buf[1] = 0x20
    buf[4] = 0x05
    buf[5] = 0x01
    buf[6] = 0x96
    buf[7] = 0xF8
    buf[8] = 0x00
    buf[9] = 0x03
    try:
        n = h.send_feature_report(bytes(buf))
        print(f"  send_feature_report 返回 = {n}")
    except Exception as e:
        print(f"  send 异常 {type(e).__name__}: {e}")
    print()

    print("  等一下再 GET...")
    for i in range(6):
        time.sleep(0.05)
        try:
            r = h.get_feature_report(0x0E, 65)
            if r and any(r):
                show(f"try#{i}", r)
                break
            else:
                show(f"try#{i}", r)
        except Exception as e:
            print(f"  try#{i}: 异常 {type(e).__name__}: {e}")
    print()

    # --- D. 打印设备 feature report 能力 (如果 hidapi 支持) ---
    print("[D] 设备信息")
    try:
        for d in hid.enumerate():
            if d.get("vendor_id") == 0x27C6 and d.get("usage_page") == 0xFF00:
                for k, v in d.items():
                    if k != "path":
                        print(f"  {k} = {v}")
    except Exception as e:
        print(f"  异常: {e}")

    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
