# run-watch.ps1 — 全集合只读监听 + 触点轨迹记录
#   * 对 GXTP5100 的 Col01/Col02/Col03/Col04 各开只读句柄监听输入报文（绝不写入）
#   * 同时以轨迹模式记录触控板触点（接触数 / X / Y / 压力 / 毫秒时间戳）
# 用法: pwsh -File run-watch.ps1 -Seconds 720
param([int]$Seconds = 720)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$log  = Join-Path $here 'watch-log.txt'

Add-Type -Path (Join-Path $here 'RawTouchProbe.cs')
Add-Type -Path (Join-Path $here 'HidWatch.cs')

function Write-Log([string]$s) { $s | Out-File -FilePath $log -Append -Encoding utf8 }

"=== watch start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff')  duration=${Seconds}s ===" | Out-File -FilePath $log -Encoding utf8

$r = [HidWatch]::StartMany('GXTP5100', @('Col01', 'Col02', 'Col03', 'Col04'))
Write-Log "集合打开结果: $r"

[RawTouchProbe]::TraceMode = $true
$p = [RawTouchProbe]::Start($true, $false)
Write-Log "触点轨迹: $p"
Write-Log "--- 格式说明: [TRACE] t=秒 n=接触数 [触点ID:x X坐标 y Y坐标 p 压力] ; [W ColXX #n] = 该集合收到的报文 ; [MAXP] 压力峰值 ---"

$deadline = [DateTime]::Now.AddSeconds($Seconds)
while ([DateTime]::Now -lt $deadline) {
    [RawTouchProbe]::Pump(100) | Out-Null
    foreach ($l in [RawTouchProbe]::Drain()) { Write-Log $l }
    foreach ($l in [HidWatch]::Drain())     { Write-Log $l }
}

[HidWatch]::StopAll()
Start-Sleep -Milliseconds 600
foreach ($l in [HidWatch]::Drain())     { Write-Log $l }
foreach ($l in [RawTouchProbe]::Drain()) { Write-Log $l }

Write-Log "=== end $(Get-Date -Format 'HH:mm:ss')  HID报文总数=$([HidWatch]::TotalReports) ==="
