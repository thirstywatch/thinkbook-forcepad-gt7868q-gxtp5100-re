# gtx8-write-fixed.ps1 —— 按 Goodix 官方 GTX8 源码修正帧格式后重测写入
# 关键修正: hidbuf[4] = data_sz + 5 (不是 +7)；raw 模式 = 3×disable + 1×confirm + 读回校验
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$logf = Join-Path $here 'gtx8-write-log.txt'
Add-Type -Path @(
    (Join-Path $here 'ColProbe.cs'),
    (Join-Path $here 'Gx.cs'),
    (Join-Path $here 'WriteHelper.cs')
) -ErrorAction Stop

function Say($s) { Write-Output $s; Add-Content -Path $logf -Value $s -Encoding utf8 }
Set-Content -Path $logf -Value ("=== GTX8 corrected-framing write " + (Get-Date -Format s) + " ===") -Encoding utf8

Say ("Col02 open: " + [ColProbe]::OpenPath([ColProbe]::FindPath('&col02'), $false, $true))
$wo = [ColProbe]::OpenPath([ColProbe]::FindPath('&col02'), $false, $true)
Say ("Gx open: " + [Gx]::Open())

# ---- 0) 确认阈值字段是否还在 0x5B96 (重启设备后地址可能变) ----
Say "`n[0] 当前 0x5B8E 起 32 字节"
$log = ''; $base = [Gx]::Read(0x5B8E, 32, [ref]$log)
Say ("   " + $log)
if ($base) { Say ("   " + [Gx]::Hex($base, 32)) }

# ---- 1) 用【修正后的 GTX8 帧】写 0x5B96 <- 25 x8 ----
Say "`n[1] 修正帧写入 0x5B96 <- 25 (hidbuf[4] = len+5)"
$new = New-Object byte[] 16
for ($i = 0; $i -lt 16; $i += 2) { $new[$i] = 25 }
$log = ''
$r1 = [GTX8]::Write16($wo, 0x5B96, $new)
Say ("   " + $r1)
Start-Sleep -Milliseconds 300
$log = ''; $c1 = [Gx]::Read(0x5B8E, 32, [ref]$log)
Say ("   回读: " + $(if ($c1) { [Gx]::Hex($c1, 32) } else { '失败' }))
$ok1 = $false
if ($c1 -and $c1.Length -ge 16 -and $c1[8] -eq 25) { $ok1 = $true }
Say ("   => " + $(if ($ok1) { "★ 写入生效!!" } else { "未生效，继续试 raw 模式" }))

if (-not $ok1) {
    # ---- 2) 按官方序列进入 raw 模式 ----
    Say "`n[2] 官方 raw 模式序列: 3x {33 00 CD} + 1x {35 00 CB} + 读回校验"
    for ($k = 0; $k -lt 3; $k++) {
        Say ("    disable #" + ($k + 1) + ": " + [GTX8]::Write16($wo, 0x60CC, [byte[]](0x33, 0x00, 0xCD)))
        Start-Sleep -Milliseconds 10
    }
    Say ("    confirm: " + [GTX8]::Write16($wo, 0x60CC, [byte[]](0x35, 0x00, 0xCB)))
    Start-Sleep -Milliseconds 30
    $log = ''; $cf = [Gx]::Read(0x60CC, 3, [ref]$log)
    Say ("    读回 0x60CC: " + $(if ($cf) { [Gx]::Hex($cf, 3) } else { '失败' }) + "   (官方要求 buf[1] == 1)")

    # ---- 3) 再写阈值 ----
    Say "`n[3] 在 raw 模式下再写一次阈值"
    Say ("   " + [GTX8]::Write16($wo, 0x5B96, $new))
    Start-Sleep -Milliseconds 300
    $log = ''; $c2 = [Gx]::Read(0x5B8E, 32, [ref]$log)
    Say ("   回读: " + $(if ($c2) { [Gx]::Hex($c2, 32) } else { '失败' }))

    # ---- 4) 复位 + 回 PTP 模式 (官方收尾序列) ----
    Say "`n[4] 官方收尾: 软复位 (0E 13) + 切回 PTP 模式 (03 03)"
    Say ("   " + [GTX8]::SendCmd($wo, [byte[]](0x0E, 0x13, 0x00, 0x00, 0x01, 0x01)))
    Start-Sleep -Milliseconds 150
    Say ("   " + [GTX8]::SendCmd($wo, [byte[]](0x03, 0x03, 0x00, 0x00, 0x01, 0x01)))
    Start-Sleep -Milliseconds 300
    $log = ''; $c3 = [Gx]::Read(0x5B8E, 32, [ref]$log)
    Say ("   复位后回读: " + $(if ($c3) { [Gx]::Hex($c3, 32) } else { '失败' }))
}
[ColProbe]::Close($wo)
Say "`n完成"
