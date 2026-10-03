# run-probe.ps1 — 启动触控板原始报文探针，持续记录到 probe-log.txt
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$log  = Join-Path $here 'probe-log.txt'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -Path (Join-Path $here 'RawTouchProbe.cs')

"=== probe start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -FilePath $log -Encoding utf8
$r = [RawTouchProbe]::Start($true, $false)
"start: $r" | Out-File -FilePath $log -Append -Encoding utf8

$deadline = (Get-Date).AddSeconds(600)
$reports = 0
$lastBeat = Get-Date
while ((Get-Date) -lt $deadline) {
    [RawTouchProbe]::Pump(400) | Out-Null
    $lines = [RawTouchProbe]::Drain()
    if ($lines.Count -gt 0) {
        $lines | Out-File -FilePath $log -Append -Encoding utf8
        $reports += ($lines | Where-Object { $_ -like 'RPT *' }).Count
    }
    if (((Get-Date) - $lastBeat).TotalSeconds -ge 30) {
        "--- alive $(Get-Date -Format 'HH:mm:ss') reports=$reports ---" | Out-File -FilePath $log -Append -Encoding utf8
        $lastBeat = Get-Date
    }
    if ($reports -ge 400) {
        "=== early stop: captured $reports reports ===" | Out-File -FilePath $log -Append -Encoding utf8
        break
    }
}
"=== probe end $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') totalReports=$reports ===" | Out-File -FilePath $log -Append -Encoding utf8
