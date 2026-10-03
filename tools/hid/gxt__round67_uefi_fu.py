#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND67 - 查 UEFI Firmware Update (FU) 设备与资源状态
确认 Goodix 触控板胶囊的 UEFI\RES_{b6ae105a-...} 设备是否存在、绑了什么驱动
"""
import subprocess
import json
import sys

PS1 = r'''
$ErrorActionPreference = "SilentlyContinue"
$out = [ordered]@{}

# 1. Firmware 类设备 (ClassGuid f2e7dd72-...)
$out.fw_class_devices = @()
Get-PnpDevice -PresentOnly | Where-Object { $_.Class -eq "Firmware" } | ForEach-Object {
    $out.fw_class_devices += "$($_.Status)  $($_.FriendlyName)  $($_.InstanceId)"
}

# 2. 直接按实例 ID 找那个 RES 设备
$out.res_device = @()
foreach ($inst in @(
  'UEFI\RES_{b6ae105a-ba93-4fc8-aa28-e63903ffedde}\0',
  'UEFI\RES_{b6ae105a-ba93-4fc8-aa28-e63903ffedde}',
  'SWD\UEFI\RES_{b6ae105a-ba93-4fc8-aa28-e63903ffedde}')) {
    $d = Get-PnpDevice -InstanceId $inst
    if ($d) {
        $out.res_device += "FOUND: $($d.Status)  $($d.FriendlyName)  $($d.Class)  $inst"
        $p = Get-PnpDeviceProperty -InstanceId $inst
        foreach ($n in @('DEVPKEY_Device_DriverVersion','DEVPKEY_Device_DriverProvider',
                         'DEVPKEY_Device_DriverDesc','DEVPKEY_Device_DriverInfPath')) {
            $v = ($p | Where-Object { $_.KeyName -eq $n }).Data
            if ($v) { $out.res_device += "    $($n -replace 'DEVPKEY_Device_','') = $v" }
        }
    } else {
        $out.res_device += "NOT PRESENT: $inst"
    }
}

# 3. 所有 UEFI\RES_ 设备 (看这台机器有哪些 FU 资源)
$out.all_res = @()
Get-PnpDevice | Where-Object { $_.InstanceId -match 'UEFI\\RES_' } | ForEach-Object {
    $out.all_res += "$($_.Status)  $($_.Class)  $($_.FriendlyName)  $($_.InstanceId)"
}

# 4. 固件资源表 (ESRT) - 通过 msinfo32 或注册表
$out.esrt = @()
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\mssmbios' | Out-Null
$fw = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Firmware'
if (Test-Path $fw) {
    Get-ChildItem $fw -Recurse | ForEach-Object { $out.esrt += $_.Name }
} else { $out.esrt += "(无 Firmware 注册表项)" }

$out | ConvertTo-Json -Depth 5
'''


def main():
    print("=" * 82)
    print("ROUND67 UEFI Firmware Update 设备与资源状态")
    print("=" * 82)
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS1],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        d = json.loads(r.stdout.strip())
    except Exception:
        print(r.stdout[:6000]); print("ERR:", r.stderr[:2000]); return 1

    for sec, title in [("fw_class_devices", "1. Class=Firmware 的在位设备"),
                       ("res_device", "2. Goodix RES 设备 {b6ae105a-...}"),
                       ("all_res", "3. 机器上全部 UEFI\\RES_ 设备"),
                       ("esrt", "4. 固件注册表项")]:
        print(f"\n--- {title} ---")
        v = d.get(sec) or ["(空)"]
        for x in v:
            print("  " + str(x))
    return 0


if __name__ == "__main__":
    sys.exit(main())
