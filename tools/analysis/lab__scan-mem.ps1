# scan-mem.ps1 —— 把 Goodix 芯片 16 位地址空间整块读下来（纯读，非破坏性）
# 输出: mem-scan-16bit.txt —— 每行 "0xADDR hex..."
$ErrorActionPreference = 'Continue'
Add-Type -Path @("$PSScriptRoot\ColProbe.cs", "$PSScriptRoot\Gx.cs") -ErrorAction Stop
$r = [Gx]::Open()
Write-Output "open: $r"
if ($r -ne 'ok') { exit 1 }

$out = Join-Path $PSScriptRoot 'mem-scan-16bit.txt'
Set-Content -Path $out -Value "# Goodix 16-bit address space dump  $(Get-Date -Format s)"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$buf = New-Object System.Collections.Generic.List[string]
$ok = 0; $fail = 0
for ($a = 0; $a -lt 0x10000; $a += 60) {
    $log = ''
    $d = [Gx]::Read($a, 60, [ref]$log)
    if ($d) {
        $hex = ($d | ForEach-Object { $_.ToString('X2') }) -join ' '
        $buf.Add(("0x{0:X4} {1}" -f $a, $hex))
        $ok++
    }
    else {
        $buf.Add(("0x{0:X4} <FAIL {1}>" -f $a, $log))
        $fail++
    }
    if ($buf.Count -ge 64) { Add-Content -Path $out -Value $buf; $buf.Clear() }
    Start-Sleep -Milliseconds 15
}
if ($buf.Count -gt 0) { Add-Content -Path $out -Value $buf }
Write-Output ("done: ok={0} fail={1} elapsed={2:N1}s -> {3}" -f $ok, $fail, $sw.Elapsed.TotalSeconds, $out)
