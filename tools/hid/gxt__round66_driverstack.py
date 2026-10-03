#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND66 - 取证: 本机 GXTP5100 的驱动栈 + 是否有官方固件更新组件
用 PowerShell 采集, 判断 Windows 侧有没有可用的官方刷写通路。
"""
import subprocess
import json
import sys

PS1 = r'''
$ErrorActionPreference = "SilentlyContinue"
$out = [ordered]@{}

# 1. GXTP5100 三个接口的驱动信息
$out.devices = @()
foreach ($inst in @(
    'ACPI\GXTP5100\1',
    'HID\GXTP5100&COL01\5&52A7AED&0&0000',
    'HID\GXTP5100&COL02\5&52A7AED&0&0001',
    'HID\GXTP5100&COL03\5&52A7AED&0&0002',
    'HID\GXTP5100&COL04\5&52A7AED&0&0003')) {
    $p = Get-PnpDeviceProperty -InstanceId $inst
    $rec = [ordered]@{ instance = $inst }
    foreach ($n in @('DEVPKEY_Device_DriverVersion','DEVPKEY_Device_DriverProvider',
                     'DEVPKEY_Device_DriverDesc','DEVPKEY_Device_DriverInfPath',
                     'DEVPKEY_Device_DriverDate','DEVPKEY_Device_Driver')) {
        $v = ($p | Where-Object { $_.KeyName -eq $n }).Data
        if ($v) { $rec[$n -replace 'DEVPKEY_Device_',''] = "$v" }
    }
    $out.devices += $rec
}

# 2. 系统里所有含 goodix 的驱动文件/服务
$out.driver_files = @()
Get-ChildItem -Path C:\Windows\System32\drivers -Filter "*goodix*" | ForEach-Object {
    $out.driver_files += "$($_.Name)  $($_.Length) B  $($_.LastWriteTime)"
}
Get-ChildItem -Path C:\Windows\System32 -Filter "*goodix*" | ForEach-Object {
    $out.driver_files += "$($_.Name)  $($_.Length) B  $($_.LastWriteTime)"
}

# 3. DriverStore 里的 Goodix 包
$out.driverstore = @()
Get-ChildItem -Path C:\Windows\System32\DriverStore\FileRepository -Directory |
    Where-Object { $_.Name -match 'goodix|gxtp|gt7868|hidi2c|touchpad' } |
    ForEach-Object { $out.driverstore += $_.Name }

# 4. 已安装程序里找 Goodix / 触控板厂商工具
$out.installed = @()
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*,
                 HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* |
    Where-Object { $_.DisplayName -match 'Goodix|Touchpad|Touch Pad|触控|Zero Touch|Intelligent Sensing' } |
    ForEach-Object { $out.installed += "$($_.DisplayName)  v$($_.DisplayVersion)  $($_.InstallLocation)" }

# 5. 有无 Goodix 相关的服务/内核驱动在跑
$out.services = @()
Get-CimInstance Win32_SystemDriver | Where-Object { $_.Name -match 'goodix|gxtp|hidi2c' } |
    ForEach-Object { $out.services += "$($_.Name)  $($_.State)  $($_.PathName)" }

$out | ConvertTo-Json -Depth 5
'''

def main():
    print("=" * 82)
    print("ROUND66 GXTP5100 驱动栈取证")
    print("=" * 82)
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                        "-Command", PS1],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print("PS stderr:", r.stderr[:2000])
    txt = r.stdout.strip()
    try:
        d = json.loads(txt)
    except Exception:
        print(txt[:6000])
        return 1

    print("\n--- 1. 设备驱动 ---")
    for rec in d.get("devices", []):
        print(f"  {rec.get('instance')}")
        for k, v in rec.items():
            if k != "instance":
                print(f"      {k:18s} = {v}")
    print("\n--- 2. 驱动文件 ---")
    for f in d.get("driver_files", []) or ["(无)"]:
        print("  " + f)
    print("\n--- 3. DriverStore 包 ---")
    for f in d.get("driverstore", []) or ["(无)"]:
        print("  " + f)
    print("\n--- 4. 已安装相关程序 ---")
    for f in d.get("installed", []) or ["(无)"]:
        print("  " + f)
    print("\n--- 5. 内核驱动/服务 ---")
    for f in d.get("services", []) or ["(无)"]:
        print("  " + f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
