#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND68 - 挖本机 GXTP5100 的 ACPI 描述符 + I2C 控制器信息
目的: 拿到 wCommandRegister/wDataRegister/wInputRegister 等寄存器地址,
      以及 I2C 从地址, 判断能否走"直接操作 I2C 控制器"的路子。
"""
import subprocess
import json
import sys

PS1 = r'''
$ErrorActionPreference = "SilentlyContinue"
$out = [ordered]@{}

# 1. 找 GXTP5100 挂在哪个 I2C 控制器上
$out.parent = @()
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like '*GXTP5100*' } | ForEach-Object {
    $p = Get-PnpDeviceProperty -InstanceId $_.InstanceId -ErrorAction SilentlyContinue
    $parent = ($p | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_Parent' }).Data
    $out.parent += "$($_.InstanceId)  -> parent = $parent"
}

# 2. Intel Serial IO I2C 控制器
$out.i2c_ctl = @()
Get-PnpDevice -PresentOnly | Where-Object {
    $_.FriendlyName -match 'I2C|Serial IO|SMBus|SPI'
} | ForEach-Object {
    $out.i2c_ctl += "$($_.Status)  [$($_.Class)]  $($_.FriendlyName)  $($_.InstanceId)"
}

# 3. ACPI 固件表 - 导出 MSDM/DSDT 之类信息
$out.acpi_ver = (Get-CimInstance Win32_ComputerSystemProduct | Select-Object -First 1).Version
try { $out.bios = (Get-CimInstance Win32_BIOS | Select-Object SMBIOSBIOSVersion,SerialNumber,Manufacturer | ConvertTo-Json -Compress) } catch {}

# 4. 尝试读取 ACPI 表 (需要管理员, 可能失败)
$out.acpi_tables = @()
$acpiDir = "$env:SystemRoot\System32\drivers\etc"
Get-ChildItem "$env:SystemRoot\System32\config\ACPI" -ErrorAction SilentlyContinue | Select-Object -First 5 | ForEach-Object { $out.acpi_tables += $_.Name }

# 5. 所有 HID 设备的 ACPI 路径 (ACPI\GXTP5100\1 的完整链)
$out.hid_acpi = @()
Get-PnpDevice -PresentOnly -Class HIDClass | ForEach-Object {
    $p = Get-PnpDeviceProperty -InstanceId $_.InstanceId -ErrorAction SilentlyContinue
    $parent = ($p | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_Parent' }).Data
    $out.hid_acpi += "$($_.InstanceId)  parent=$parent"
}

$out | ConvertTo-Json -Depth 5
'''

PS2 = r'''
# 尝试用 ACPI 工具导出 DSDT（需要管理员）
$ErrorActionPreference = "SilentlyContinue"
"=== 管理员权限检测 ==="
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
"IsAdmin: " + $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
"=== Intel Serial IO 驱动 ==="
Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -match 'I2C|Serial IO|GPIO' } |
  Select-Object DeviceName,DriverVersion,DriverProviderName,InfName | Format-Table -AutoSize | Out-String -Width 200
'''


def run(ps):
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout


def main():
    print("=" * 82)
    print("ROUND68 GXTP5100 ACPI 描述符 + I2C 控制器取证")
    print("=" * 82)
    out = run(PS1)
    try:
        d = json.loads(out.strip())
    except Exception:
        print(out[:5000]); return 1

    print("\n--- 1. GXTP5100 设备父子关系 ---")
    for x in d.get("parent") or ["(无)"]:
        print("  " + str(x))
    print("\n--- 2. I2C / Serial IO 控制器 ---")
    for x in d.get("i2c_ctl") or ["(无)"]:
        print("  " + str(x))
    print("\n--- 3. BIOS ---")
    print("  " + str(d.get("bios")))
    print("\n--- 4. HID 设备 ACPI 路径 ---")
    for x in d.get("hid_acpi") or ["(无)"]:
        print("  " + str(x))

    print("\n" + "=" * 82)
    print("ROUND68b 管理员权限 + 驱动版本")
    print("=" * 82)
    print(run(PS2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
