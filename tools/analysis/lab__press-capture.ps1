# press-capture.ps1 —— 25 秒原始报文捕获（记录压力与 Tip Switch，用于测定点击阈值）
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$log = Join-Path $here 'press-log.txt'
Add-Type -Path (Join-Path $here 'RawTouchProbe.cs') -ErrorAction Stop
[RawTouchProbe]::TraceMode = $false
[RawTouchProbe]::RawLimit = 100000
Set-Content -Path $log -Value ("=== press capture " + (Get-Date -Format s) + " ===") -Encoding utf8
$r = [RawTouchProbe]::Start($true, $false)   # 触控板(+触摸屏枚举)，与 run-probe.ps1 相同参数
Write-Output "start: $r"
[RawTouchProbe]::Pump(300) | Out-Null
$deadline = (Get-Date).AddSeconds(25)
$n = 0
while ((Get-Date) -lt $deadline) {
    [RawTouchProbe]::Pump(200) | Out-Null
    $lines = [RawTouchProbe]::Drain()
    if ($lines.Count -gt 0) {
        $lines | Add-Content -Path $log -Encoding utf8
        $n += $lines.Count
    }
}
"captured lines: $n -> $log"
Get-Content $log -Tail 6

