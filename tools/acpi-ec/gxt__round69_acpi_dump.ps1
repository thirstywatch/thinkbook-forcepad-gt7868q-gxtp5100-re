# =============================================================================
# ROUND69 - READ-ONLY ACPI / device info dump
# =============================================================================
# Purpose: dump GXTP5100 touchpad ACPI definition to obtain:
#            - I2C Connection ID  (needed by an SPB client driver)
#            - I2C slave address
#            - HID Descriptor Register address
#            - GPIO interrupt pin
#
# SAFETY: THIS SCRIPT IS READ-ONLY.
#   - Does NOT write or modify any ACPI table
#   - Does NOT load or unload any driver
#   - Only queries system APIs and reads registry
#
# Usage (as Administrator):
#   powershell -NoProfile -ExecutionPolicy Bypass -File round69_acpi_dump.ps1
#
# NOTE: This file is intentionally pure ASCII. PowerShell 5.1 reads .ps1
#       using the system ANSI codepage (GBK on zh-CN), which corrupts
#       UTF-8 Chinese comments and breaks string parsing.
# =============================================================================

$ErrorActionPreference = "SilentlyContinue"
$ProgressPreference = "SilentlyContinue"

$OutDir = Join-Path $PSScriptRoot "round69_acpi_out"
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

function Write-OutFile2 {
    param([string]$Name, [string]$Content)
    $path = Join-Path $OutDir $Name
    $Content | Out-File -FilePath $path -Encoding UTF8
    Write-Host ("  [wrote] " + $Name) -ForegroundColor Green
}

Write-Host "=============================================================="
Write-Host "ROUND69 READ-ONLY ACPI / DEVICE INFO DUMP"
Write-Host "=============================================================="

# --- privilege check ---
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
$IsAdmin = $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host ""
Write-Host ("IsAdmin: " + $IsAdmin)
if (-not $IsAdmin) {
    Write-Host "  WARNING: not admin - ACPI table dump will be skipped"
}
Write-Host ""

# =============================================================
# 1. GXTP5100 full device properties
# =============================================================
Write-Host "[1] GXTP5100 device properties"

$devs = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'GXTP5100' }
$buf = New-Object System.Collections.ArrayList
[void]$buf.Add("=== GXTP5100 device instances ===")
foreach ($d in $devs) {
    [void]$buf.Add("")
    [void]$buf.Add("--- " + $d.InstanceId + " ---")
    [void]$buf.Add("  Status : " + $d.Status)
    [void]$buf.Add("  Class  : " + $d.Class)
    [void]$buf.Add("  Name   : " + $d.FriendlyName)
    $p = Get-PnpDeviceProperty -InstanceId $d.InstanceId
    foreach ($prop in ($p | Sort-Object KeyName)) {
        $val = $prop.Data
        if ($null -eq $val) { continue }
        if ($val -is [array]) { $val = ($val -join " | ") }
        $k = $prop.KeyName -replace '^DEVPKEY_', ''
        [void]$buf.Add("    " + $k + " = " + $val)
    }
}
Write-OutFile2 "01_gxtp5100_properties.txt" ($buf -join "`r`n")

# =============================================================
# 2. I2C controller details
# =============================================================
Write-Host "[2] Intel Serial IO I2C controller details"

$buf2 = New-Object System.Collections.ArrayList
[void]$buf2.Add("=== I2C / SPI / GPIO controllers ===")
$ctl = Get-PnpDevice -PresentOnly | Where-Object {
    $_.FriendlyName -match 'I2C|Serial IO|SPI|SMBus|GPIO'
}
foreach ($d in $ctl) {
    [void]$buf2.Add("")
    [void]$buf2.Add("--- " + $d.InstanceId + " ---")
    [void]$buf2.Add("  Status: " + $d.Status + "   Name: " + $d.FriendlyName)
    $p = Get-PnpDeviceProperty -InstanceId $d.InstanceId
    foreach ($n in @('DEVPKEY_Device_DriverVersion',
                     'DEVPKEY_Device_DriverProvider',
                     'DEVPKEY_Device_DriverInfPath',
                     'DEVPKEY_Device_Parent',
                     'DEVPKEY_Device_HardwareIds',
                     'DEVPKEY_Device_LocationInfo',
                     'DEVPKEY_Device_BusNumber')) {
        $v = ($p | Where-Object { $_.KeyName -eq $n }).Data
        if ($v) {
            if ($v -is [array]) { $v = ($v -join " | ") }
            $kk = $n -replace 'DEVPKEY_Device_', ''
            [void]$buf2.Add("    " + $kk + " = " + $v)
        }
    }
}
Write-OutFile2 "02_i2c_controllers.txt" ($buf2 -join "`r`n")

# =============================================================
# 3. ACPI tables (admin only)
# =============================================================
Write-Host "[3] ACPI tables"

if ($IsAdmin) {

    # 3a. all ACPI\ devices with full properties
    $buf3 = New-Object System.Collections.ArrayList
    [void]$buf3.Add("=== all ACPI devices, full properties ===")
    Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^ACPI\\' } | ForEach-Object {
        [void]$buf3.Add("")
        [void]$buf3.Add("### " + $_.InstanceId + "  [" + $_.FriendlyName + "]")
        $p = Get-PnpDeviceProperty -InstanceId $_.InstanceId
        foreach ($prop in ($p | Sort-Object KeyName)) {
            $v = $prop.Data
            if ($null -eq $v) { continue }
            if ($v -is [array]) { $v = ($v -join " | ") }
            $k = $prop.KeyName -replace '^DEVPKEY_', ''
            [void]$buf3.Add("    " + $k + " = " + $v)
        }
    }
    Write-OutFile2 "03_acpi_devices.txt" ($buf3 -join "`r`n")

    # 3b. WMI ACPI classes
    $buf4 = New-Object System.Collections.ArrayList
    [void]$buf4.Add("=== ACPI raw export attempts ===")
    [void]$buf4.Add("")
    try {
        $msacpi = Get-WmiObject -Namespace "root\wmi" -Class "MSAcpi_*" -ErrorAction SilentlyContinue
        if ($msacpi) {
            [void]$buf4.Add("found MSAcpi_* classes:")
            foreach ($m in $msacpi) { [void]$buf4.Add("  " + $m) }
        } else {
            [void]$buf4.Add("no MSAcpi_* WMI classes found")
        }
    } catch {
        [void]$buf4.Add("MSAcpi query failed")
    }
    [void]$buf4.Add("")
    [void]$buf4.Add("--- registry HKLM\SYSTEM\CurrentControlSet\Enum\ACPI ---")
    $acpiKey = "HKLM:\SYSTEM\CurrentControlSet\Enum\ACPI"
    if (Test-Path $acpiKey) {
        Get-ChildItem $acpiKey -ErrorAction SilentlyContinue | ForEach-Object {
            [void]$buf4.Add("  " + $_.PSChildName)
        }
    }
    Write-OutFile2 "04_acpi_registry.txt" ($buf4 -join "`r`n")

    # 3c. GXTP5100 registry details (may hold SPB connection params)
    $buf5 = New-Object System.Collections.ArrayList
    [void]$buf5.Add("=== GXTP5100 registry details ===")
    $base = "HKLM:\SYSTEM\CurrentControlSet\Enum\ACPI\GXTP5100"
    if (Test-Path $base) {
        Get-ChildItem $base -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
            [void]$buf5.Add("")
            [void]$buf5.Add("### " + $_.Name)
            $props = Get-ItemProperty -Path $_.PSPath -ErrorAction SilentlyContinue
            if ($props) {
                $props.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS' } | ForEach-Object {
                    $v = $_.Value
                    if ($v -is [byte[]]) {
                        $hex = ($v | ForEach-Object { $_.ToString("X2") }) -join " "
                        $v = "BYTES(" + $v.Length + "): " + $hex
                    } elseif ($v -is [array]) {
                        $v = ($v -join " | ")
                    }
                    [void]$buf5.Add("    " + $_.Name + " = " + $v)
                }
            }
        }
    } else {
        [void]$buf5.Add("path not found: " + $base)
    }
    Write-OutFile2 "05_gxtp5100_registry.txt" ($buf5 -join "`r`n")

    # 3d. SPB connection clues
    $buf6 = New-Object System.Collections.ArrayList
    [void]$buf6.Add("=== SPB / GPIO connection resources (Connection ID hunt) ===")
    [void]$buf6.Add("")
    foreach ($inst in @('ACPI\GXTP5100\1')) {
        $p = Get-PnpDeviceProperty -InstanceId $inst -ErrorAction SilentlyContinue
        foreach ($prop in ($p | Sort-Object KeyName)) {
            $v = $prop.Data
            if ($null -eq $v) { continue }
            if ($v -is [array]) { $v = ($v -join " | ") }
            $k = $prop.KeyName -replace '^DEVPKEY_', ''
            [void]$buf6.Add("  " + $inst + " :: " + $k + " = " + $v)
        }
    }
    [void]$buf6.Add("")
    [void]$buf6.Add("--- search registry for Connection / Spb / Resource ---")
    [void]$buf6.Add("check: HKLM\SYSTEM\CurrentControlSet\Enum\ACPI\GXTP5100\1\Device Parameters")
    Write-OutFile2 "06_spb_connections.txt" ($buf6 -join "`r`n")

    # 3e. Intel Serial IO child devices (each I2C target appears as a child)
    $buf7 = New-Object System.Collections.ArrayList
    [void]$buf7.Add("=== children of each Intel I2C controller (mapping target -> bus) ===")
    Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'I2C Host Controller' } | ForEach-Object {
        $ctlInst = $_.InstanceId
        [void]$buf7.Add("")
        [void]$buf7.Add("### " + $_.FriendlyName)
        [void]$buf7.Add("    " + $ctlInst)
        $children = Get-PnpDevice -PresentOnly | Where-Object {
            $pp = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -ErrorAction SilentlyContinue |
                   Where-Object { $_.KeyName -eq 'DEVPKEY_Device_Parent' }).Data
            $pp -eq $ctlInst
        }
        if ($children) {
            foreach ($c in $children) {
                [void]$buf7.Add("      child: " + $c.InstanceId + "  [" + $c.FriendlyName + "]")
            }
        } else {
            [void]$buf7.Add("      (no present children)")
        }
    }
    Write-OutFile2 "07_i2c_children.txt" ($buf7 -join "`r`n")

} else {
    Write-OutFile2 "03_acpi_devices_SKIPPED.txt" "admin required - ACPI dump skipped"
}

# =============================================================
# 4. summary
# =============================================================
Write-Host "[4] summary"

$sum = New-Object System.Collections.ArrayList
[void]$sum.Add("==============================================")
[void]$sum.Add("ROUND69 SUMMARY")
[void]$sum.Add("==============================================")
[void]$sum.Add("")
[void]$sum.Add("time : " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
[void]$sum.Add("admin: " + $IsAdmin)
[void]$sum.Add("")
[void]$sum.Add("--- GXTP5100 device tree ---")
foreach ($d in $devs) {
    $parent = (Get-PnpDeviceProperty -InstanceId $d.InstanceId |
               Where-Object { $_.KeyName -eq 'DEVPKEY_Device_Parent' }).Data
    [void]$sum.Add("  " + $d.InstanceId)
    [void]$sum.Add("      parent = " + $parent)
}
[void]$sum.Add("")
[void]$sum.Add("--- I2C host controllers ---")
Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'I2C Host Controller' } | ForEach-Object {
    [void]$sum.Add("  " + $_.FriendlyName)
    [void]$sum.Add("      " + $_.InstanceId)
}
[void]$sum.Add("")
[void]$sum.Add("--- what to look for next ---")
[void]$sum.Add("  [ ] ConnectionId (like \_SB.PCI0.I2C?.XXXX or a numeric handle) in 03/05/06")
[void]$sum.Add("  [ ] GXTP5100 _CRS resources (I2cSerialBus / GpioInt) in 03")
[void]$sum.Add("  [ ] I2C slave address (often 0x2C or 0x5D)")
[void]$sum.Add("  [ ] which controller hosts GXTP5100 in 07")
Write-OutFile2 "00_SUMMARY.txt" ($sum -join "`r`n")

Write-Host ""
Write-Host "=============================================================="
Write-Host ("DONE. Output dir: " + $OutDir)
Write-Host "=============================================================="
Write-Host ""
foreach ($l in $sum) { Write-Host $l }
