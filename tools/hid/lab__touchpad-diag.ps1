# touchpad-diag.ps1 —— 触控板模块诊断（换模块后一键抓全信息）
#
# 用途：换上 X9-15（或其他）模块后，跑这一个脚本，即可判定：
#   ① Windows 是否枚举到设备 · 故障码（是否是 Code 10）
#   ② HID 集合（Col01..Col04）是否齐全
#   ③ ACPI 设备的资源回填情况
#   ④ 若 HID 通道可用，则读设备 VER_ADDR(0x4014) 看它自报的型号
#   ⑤ 相关事件日志
#
# 纯只读：只查询 + 只在 HID 可用时做设备内存【读】。

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$OUT  = Join-Path $here ('diag-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt')

function W($s) { Write-Host $s; Add-Content -LiteralPath $OUT -Value $s -Encoding utf8 }

W ("=" * 76)
W ("触控板模块诊断  {0}" -f (Get-Date -Format 's'))
W ("=" * 76)

# ── 1. ACPI / 父设备 ───────────────────────────────────────────
W ""
W "--- 1. ACPI 触控板设备 ---"
$acpi = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'GXTP|TPAD|Goodix|27C6' }
if ($acpi) {
    $acpi | ForEach-Object {
        W ("  {0,-8} {1,-14} {2}" -f $_.Status, $_.Class, $_.InstanceId)
        try {
            $p = Get-PnpDeviceProperty -InstanceId $_.InstanceId -ErrorAction SilentlyContinue |
                 Where-Object { $_.KeyName -in 'DEVPKEY_Device_ProblemCode','DEVPKEY_Device_ProblemStatus','DEVPKEY_Device_DeviceDesc','DEVPKEY_Device_HardwareIds','DEVPKEY_Device_CompatibleIds' }
            foreach ($x in $p) {
                $v = $x.Data
                if ($v -is [array]) { $v = ($v -join ' | ') }
                W ("      {0} = {1}" -f ($x.KeyName -replace 'DEVPKEY_Device_',''), $v)
            }
        } catch { W ("      <读属性失败: {0}>" -f $_.Exception.Message) }
    }
} else {
    W "  ★ 没有匹配 GXTP/TPAD/Goodix/27C6 的设备 —— 连 ACPI 层都没枚举到？"
}

# ── 2. HID 集合 ───────────────────────────────────────────────
W ""
W "--- 2. HID 集合（Col01..Col04 是否齐全）---"
$hid = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'GXTP5100&COL0' }
if ($hid) {
    foreach ($d in ($hid | Sort-Object InstanceId)) {
        W ("  {0,-8} {1,-10} {2}" -f $d.Status, $d.Class, $d.InstanceId)
    }
    $cols = @($hid | Where-Object { $_.InstanceId -match 'COL0[1-4]' })
    W ("  ⇒ HID 集合数 = {0}（正常应为 4：Col01/Col02/Col03/Col04）" -f $cols.Count)
    if ($cols.Count -lt 4) { W "  ★★ 集合不全 ⇒ 与 Code 10（读不到 HID 描述符）的症状一致" }
} else {
    W "  ★ 没有任何 GXTP5100 Col01..04 的 HID 设备 ⇒ HID 层未起来"
}

# ── 3. 故障码汇总 ─────────────────────────────────────────────
W ""
W "--- 3. 触控板相关设备的存在状态与故障码 ---"
$tp = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match 'GXTP|27C6|TPAD' }
if ($tp) {
    foreach ($d in ($tp | Sort-Object InstanceId)) {
        W ("  {0,-8} {1,-10} Problem={2,-18} {3}" -f $d.Status, $d.Class, $d.Problem, $d.InstanceId)
    }
    $bad = @($tp | Where-Object { $_.Problem -ne 'CM_PROB_NONE' })
    if ($bad.Count -gt 0) { W ("  ★★ 有 {0} 个带故障码 ⇒ 与 Code 10 预期一致" -f $bad.Count) }
} else {
    W "  ★ 没有任何【存在】的触控板设备 ⇒ ACPI 层未枚举到"
}

# ── 4. 若 HID 可用，读设备 VER_ADDR ───────────────────────────
W ""
W "--- 4. 尝试读设备 VER_ADDR (0x4014) ---"
$gx = Join-Path $here 'Gx.cs'
$cp = Join-Path $here 'ColProbe.cs'
if ((Test-Path $gx) -and (Test-Path $cp)) {
    try {
        Add-Type -Path @($cp, $gx) -ErrorAction Stop
        $r = [Gx]::Open()
        W ("  Col04 open: {0}" -f $r)
        if ($r -eq 'ok') {
            foreach ($a in 0x4014, 0x4018, 0x401C, 0x4020, 0x4024, 0x4160) {
                $wlog = ''
                $d = [Gx]::Read($a, 4, [ref]$wlog)
                if ($d -and $d.Length -ge 4) {
                    $hex = ($d | ForEach-Object { $_.ToString('X2') }) -join ' '
                    $asc = -join ($d | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } })
                    W ("    0x{0:X4} = {1}   [{2}]" -f $a, $hex, $asc)
                } else {
                    W ("    0x{0:X4} = <读失败: {1}>" -f $a, $wlog)
                }
                Start-Sleep -Milliseconds 40
            }
            W "  ⇒ 若 0x4018 = 'YELS' 则是同一家族；0x4022 起的型号串可对比（本机为 '7869'）"
        } else {
            W "  ⇒ Col04 打不开 ⇒ 无法读设备内存（符合"设备未启动"的预期）"
        }
    } catch {
        W ("  <Gx 加载/读取异常: {0}>" -f $_.Exception.Message)
    }
} else {
    W "  （找不到 Gx.cs / ColProbe.cs，跳过）"
}

# ── 5. 事件日志 ───────────────────────────────────────────────
W ""
W "--- 5. 近期与触控板/驱动相关的事件 ---"
try {
    Get-WinEvent -FilterHashtable @{ LogName='System'; StartTime=(Get-Date).AddHours(-2) } -MaxEvents 300 -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match 'GXTP|touchpad|触控板|27C6|HID' } |
        Select-Object -First 12 |
        ForEach-Object { W ("  [{0}] {1}: {2}" -f $_.TimeCreated.ToString('HH:mm:ss'), $_.ProviderName, ($_.Message -replace "`r?`n",' ').Substring(0,[Math]::Min(150,($_.Message -replace "`r?`n",' ').Length))) }
} catch { W "  <事件日志读取失败>" }

W ""
W ("报告已存: {0}" -f $OUT)
