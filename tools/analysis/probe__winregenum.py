#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""winregenum.py -- 只读方式枚举本机关键注册表项（reg.exe 被安全策略禁用，故用 winreg）
用法: python winregenum.py
"""
import sys
import winreg

HKLM = winreg.HKEY_LOCAL_MACHINE


def dump(path, max_depth=2, _d=0, _label=None):
    try:
        k = winreg.OpenKey(HKLM, path)
    except OSError as e:
        print(" " * _d + f"[!] {path}: {e}")
        return
    indent = "  " * _d
    print(f"{indent}{_label or path}")
    # values
    n_sub, n_val, _ = winreg.QueryInfoKey(k)
    for i in range(n_val):
        try:
            name, data, typ = winreg.EnumValue(k, i)
        except OSError:
            break
        if isinstance(data, bytes):
            data = data[:96].hex(" ")
            data = f"<{len(data)//3}B> {data}"
        print(f"{indent}  {name or '(default)'} = {data}")
    if _d >= max_depth:
        return
    for i in range(n_sub):
        try:
            sub = winreg.EnumKey(k, i)
        except OSError:
            break
        dump(path + "\\" + sub, max_depth, _d + 1, sub)


def main():
    targets = [
        ("DeviceGuard / HVCI", r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity", 0),
        ("DeviceGuard 全局", r"SYSTEM\CurrentControlSet\Control\DeviceGuard", 1),
        ("CI\Config（易受攻击驱动黑名单）", r"SYSTEM\CurrentControlSet\Control\CI\Config", 0),
        ("CI\Policy", r"SYSTEM\CurrentControlSet\Control\CI\Policy", 0),
    ]
    print("=" * 70)
    print(" A. 代码完整性 / 驱动黑名单")
    print("=" * 70)
    for label, path, d in targets:
        dump(path, d, 0, label + "  <" + path + ">")
    print()
    print("=" * 70)
    print(" B. I2C 控制器 (PCI 8086:7E78) 的设备节点")
    print("=" * 70)
    try:
        base = winreg.OpenKey(HKLM, r"SYSTEM\CurrentControlSet\Enum\PCI")
        n_sub, _, _ = winreg.QueryInfoKey(base)
        hits = []
        for i in range(n_sub):
            name = winreg.EnumKey(base, i)
            if "DEV_7E78" in name.upper():
                hits.append(name)
        for h in hits:
            dump(r"SYSTEM\CurrentControlSet\Enum\PCI" + "\\" + h, 2, 0, h)
    except OSError as e:
        print("[!]", e)
    print()
    print("=" * 70)
    print(" C. 触控板设备节点 (ACPI\\GXTP5100)")
    print("=" * 70)
    dump(r"SYSTEM\CurrentControlSet\Enum\ACPI\GXTP5100", 2, 0, "GXTP5100")


if __name__ == "__main__":
    main()
