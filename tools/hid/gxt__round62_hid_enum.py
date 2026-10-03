#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND62 - 枚举本机 HID 设备, 定位 Goodix GXTP5100 COL04 (Vendor-Defined)
"""
import hid
import sys

def main():
    print("=" * 82)
    print("ROUND62 本机 HID 设备枚举")
    print("=" * 82)
    all_devs = hid.enumerate()
    print(f"共 {len(all_devs)} 个 HID 设备\n")

    gx = []
    for d in all_devs:
        vid = d.get("vendor_id", 0)
        pid = d.get("product_id", 0)
        path = d.get("path", b"")
        if isinstance(path, bytes):
            path = path.decode("utf-8", "replace")
        up = d.get("usage_page", 0)
        us = d.get("usage", 0)
        mfr = d.get("manufacturer_string", "") or ""
        prod = d.get("product_string", "") or ""
        line = (f"VID={vid:04X} PID={pid:04X} UP={up:04X} U={us:04X} "
                f"if={d.get('interface_number',-1)} "
                f"mfr='{mfr}' prod='{prod}'")
        if vid == 0x27C6:
            gx.append((d, line))
            print("  ★ " + line)
            print(f"      path = {path}")
        else:
            print("    " + line)

    print()
    if not gx:
        print("!!! 未发现 VID_27C6 的 HID 设备")
        print("    可能原因: 需要管理员权限, 或设备走 I2C-HID 不暴露给 hidapi")
        return 1

    print(f"发现 {len(gx)} 个 Goodix HID 接口")
    print()
    print("=" * 82)
    print("COL04 (UP=FF00, Vendor-Defined) 候选:")
    print("=" * 82)
    for d, line in gx:
        if d.get("usage_page") == 0xFF00:
            print("  ★★ " + line)
            print(f"      path = {d.get('path')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
