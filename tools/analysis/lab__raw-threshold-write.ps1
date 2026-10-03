# raw-threshold-write.ps1 —— 进 raw 模式并把"按下阈值"70 改为 25（可回滚）
# 全程约 10 秒；raw 模式期间触控板不上报，结束后尝试自动恢复
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$logf = Join-Path $here 'threshold-log.txt'
Add-Type -Path @(
    (Join-Path $here 'ColProbe.cs'),
    (Join-Path $here 'Gx.cs'),
    (Join-Path $here 'WriteHelper.cs')
) -ErrorAction Stop

function Say($s) { Write-Output $s; Add-Content -Path $logf -Value $s -Encoding utf8 }
Set-Content -Path $logf -Value ("=== threshold write " + (Get-Date -Format s) + " ===") -Encoding utf8

Say ("open: " + [Gx]::Open())

# ---- 1) 备份当前阈值区 ----
Say "`n[1] 备份 0x5B80-0x5BE0"
$log = ''; $backup = [Gx]::Read(0x5B80, 60, [ref]$log)
Say ("   read: " + $log)
if ($backup) { Say ("   " + [Gx]::Hex($backup, 60)) }
$log = ''; $backup2 = [Gx]::Read(0x5BBC, 36, [ref]$log)
if ($backup2) { Say ("   +0x3C: " + [Gx]::Hex($backup2, 36)) }
[System.IO.File]::WriteAllBytes((Join-Path $here 'threshold-backup.bin'),
    ($(if ($backup) { $backup } else { @() }) + $(if ($backup2) { $backup2 } else { @() })))

# ---- 2) 进 raw 模式 ----
Say "`n[2] 写 0x60CC <- {33 00 CD} 进入 raw 模式"
$log = ''
[Gx]::Write(0x60CC, [byte[]](0x33, 0x00, 0xCD), [ref]$log) | Out-Null
Say ("   " + $log)
Start-Sleep -Milliseconds 400
$log = ''; $raw = [Gx]::Read(0x4100, 4, [ref]$log)
Say ("   读 0x4100 (期望 0x80): " + $log + "  " + $(if ($raw) { [Gx]::Hex($raw, 4) } else { '失败' }))

# ---- 3) 写新阈值 (0x5B96 起 8 个 70 -> 25) ----
Say "`n[3] 写新按下阈值 25 到 0x5B96 (8 个)"
$new = New-Object byte[] 16
for ($i = 0; $i -lt 16; $i += 2) { $new[$i] = 25; $new[$i + 1] = 0 }
$log = ''
$ok1 = [Gx]::Write(0x5B96, $new, [ref]$log)
Say ("   [16位帧] " + $log)
Start-Sleep -Milliseconds 200
$log = ''; $chk = [Gx]::Read(0x5B96, 16, [ref]$log)
Say ("   回读: " + $(if ($chk) { [Gx]::Hex($chk, 16) } else { '失败' }))

if (-not $chk -or $chk[0] -ne 25) {
    Say "`n[3b] 16 位帧未生效 -> 改用 32 位地址帧重试"
    $log = ''
    [Gx]::Write32(0x5B96, $new, [ref]$log) | Out-Null
    Say ("   " + $log)
    Start-Sleep -Milliseconds 200
    $log = ''; $chk = [Gx]::Read(0x5B96, 16, [ref]$log)
    Say ("   回读: " + $(if ($chk) { [Gx]::Hex($chk, 16) } else { '失败' }))
}

# ---- 4) 顺带把松开阈值 48 -> 15 也改掉 (0x5B92) ----
Say "`n[4] 写松开阈值 15 到 0x5B92"
$rel = [byte[]](15, 0, 15, 0)
$log = ''
[Gx]::Write(0x5B92, $rel, [ref]$log) | Out-Null
Say ("   " + $log)
Start-Sleep -Milliseconds 200
$log = ''; $chk2 = [Gx]::Read(0x5B8E, 32, [ref]$log)
Say ("   回读 0x5B8E: " + $(if ($chk2) { [Gx]::Hex($chk2, 32) } else { '失败' }))

# ---- 5) 尝试退出 raw 模式 ----
Say "`n[5] 尝试恢复上报"
$log = ''
[Gx]::Write(0x60CC, [byte[]](0x00, 0x00, 0x00), [ref]$log) | Out-Null
Say ("   写 0x60CC <- {00 00 00}: " + $log)
Start-Sleep -Milliseconds 300
$log = ''; $raw2 = [Gx]::Read(0x4100, 4, [ref]$log)
Say ("   读 0x4100: " + $(if ($raw2) { [Gx]::Hex($raw2, 4) } else { '失败' }))

# 再试: 通过 Col03 写 Input Mode = 3 (等价于 F8)
$p3 = [ColProbe]::FindPath('&col03')
$h3 = [ColProbe]::OpenPath($p3, $true, $true)
if ($h3 -ne [IntPtr]::Zero) {
    Say ("   " + [InputMode]::Set($h3, 3))
    [ColProbe]::Close($h3)
}
Say "`n完成。若触控板仍无反应，请运行: pnputil /restart-device ""ACPI\GXTP5100\1"""

