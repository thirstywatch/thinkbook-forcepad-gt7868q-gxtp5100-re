# calib-21.ps1 -- READ-DIRECTION ONLY. Every frame has byte[5] == 0x01 (read flag).
#   Purpose: calibrate the undocumented _I2C_INDIRECT_READ = 0x21 before using it on flash.
#   Step 1: calibrate 0x21 on a KNOWN address (0x4014, whose 0x20 read we already validated by checksum).
#   Step 2: only if step 1 looks like a read, try 0x21 with a 4-byte address on high flash.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'calib-21-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function Hexs($d) { if ($null -eq $d) { return '<null>' }; return (($d | ForEach-Object { $_.ToString('X2') }) -join ' ') }
function Asc($d) { if ($null -eq $d) { return '' }; $sb=New-Object System.Text.StringBuilder; foreach($b in $d){ if($b -ge 32 -and $b -lt 127){[void]$sb.Append([char]$b)}else{[void]$sb.Append('.')} }; return $sb.ToString() }

W ("=== 0x21 calibration (READ-ONLY frames, byte[5]=0x01) :: " + (Get-Date -Format 's') + " ===")
Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'P3.cs')) -ErrorAction Stop
$p = [ColProbe]::FindPath('Col04')
$h = [ColProbe]::OpenPath($p, $true, $true)
W ("Col04 open = " + $(if ($h -eq [IntPtr]::Zero) { 'FAILED' } else { 'ok' }) + "  path=" + (($p -replace '.*hid#','') -replace '#.*',''))
if ($h -eq [IntPtr]::Zero) { exit 1 }

$cases = @(
    @('F1 0x20 ctrl 0x4014 x32', @(0x0E,0x20,0x00,0x00,0x05,0x01,0x40,0x14,0x00,0x20)),
    @('F2 0x21     0x4014 x32', @(0x0E,0x21,0x00,0x00,0x05,0x01,0x40,0x14,0x00,0x20)),
    @('F3 0x21 ctrl 0x8400 x16', @(0x0E,0x21,0x00,0x00,0x05,0x01,0x84,0x00,0x00,0x10)),
    @('F4 0x20 ctrl 0x8400 x16', @(0x0E,0x20,0x00,0x00,0x05,0x01,0x84,0x00,0x00,0x10)),
    @('F5 0x21 a32 0x00010000 x32', @(0x0E,0x21,0x00,0x00,0x07,0x01,0x00,0x01,0x00,0x00,0x00,0x20)),
    @('F6 0x21 a32 0x00019000 x32', @(0x0E,0x21,0x00,0x00,0x07,0x01,0x00,0x01,0x90,0x00,0x00,0x20)),
    @('F7 0x20 a32 0x00010000 x32', @(0x0E,0x20,0x00,0x00,0x07,0x01,0x00,0x01,0x00,0x00,0x00,0x20))
)
foreach ($c in $cases) {
    $lbl = $c[0]; $pkt = [byte[]]$c[1]
    $lg = ''
    $d = [P3]::Raw($h, $pkt, [ref]$lg)
    W ("{0,-26} -> {1}  [{2}]   ({3})" -f $lbl, (Hexs $d), (Asc $d), $lg)
    Start-Sleep -Milliseconds 350
}
[ColProbe]::Close($h)
W "=== DONE (only read-flag frames were sent) ==="
