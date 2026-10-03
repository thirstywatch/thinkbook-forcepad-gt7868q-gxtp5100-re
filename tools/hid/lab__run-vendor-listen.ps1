# run-vendor-listen.ps1 — 只读监听 Goodix 厂商通道 (Col04)，并同步记录触控板接触数变化
# 用法: pwsh -File run-vendor-listen.ps1 -Seconds 900
param([int]$Seconds = 900)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$log  = Join-Path $here 'vendor-listen-log.txt'

Add-Type -Path (Join-Path $here 'RawTouchProbe.cs')
Add-Type -Path (Join-Path $here 'VendorListen.cs')

function Write-Log([string]$s) { $s | Out-File -FilePath $log -Append -Encoding utf8 }

"=== vendor listen start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff')  duration=${Seconds}s ===" | Out-File -FilePath $log -Encoding utf8
$v = [VendorListen]::Start('GXTP5100', 'Col04')
Write-Log "vendor: $v"
$p = [RawTouchProbe]::Start($true, $false)
Write-Log "ptp: $p"
Write-Log "device: $([VendorListen]::DevicePath)"
Write-Log "--- 说明: [VENDOR #n] = 厂商通道收到的报文; [n s] PTP contacts=x = 触控板接触数变化 ---"

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$lastCount = -1
$deadline = [DateTime]::Now.AddSeconds($Seconds)

while ([DateTime]::Now -lt $deadline -and [VendorListen]::ReportCount -lt 400) {
    [RawTouchProbe]::Pump(120) | Out-Null

    foreach ($l in [RawTouchProbe]::Drain()) {
        if ($l -match '\[TOUCH\]') {
            Write-Log ("[{0:F2}s] {1}" -f $sw.Elapsed.TotalSeconds, $l)
        }
        elseif ($l -notmatch '^RPT ' -and $l -notmatch '^\s+-> ') {
            Write-Log ("[{0:F2}s] PTP {1}" -f $sw.Elapsed.TotalSeconds, $l)
        }
    }

    foreach ($l in [VendorListen]::Drain()) { Write-Log ("[{0:F2}s] {1}" -f $sw.Elapsed.TotalSeconds, $l) }
}

[VendorListen]::Stop()
Start-Sleep -Milliseconds 400
foreach ($l in [VendorListen]::Drain()) { Write-Log ("[{0:F2}s] {1}" -f $sw.Elapsed.TotalSeconds, $l) }

Write-Log "=== end $(Get-Date -Format 'HH:mm:ss') reports=$([VendorListen]::ReportCount) idleTimeouts=$([VendorListen]::TimeoutCount) ==="
