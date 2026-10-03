# scan-stability.ps1 -- STRICTLY READ ONLY. ASCII only. Single handle.
# Purpose: map the whole 16-bit address space (probe every 0x100) and classify each 16 B window as
#   STABLE (two reads 180 ms apart are identical)  |  LIVE (they differ)  |  ERR (read failed)
# This tells us where a static config/code image could live vs where runtime state lives.
# Only read-direction frames (0E 20 00 00 05 01 addr16BE len16BE). No writes.
$root = $PSScriptRoot
$LOG  = Join-Path $root 'scan-stability.txt'
Set-Content -LiteralPath $LOG -Value ("=== stability scan :: " + (Get-Date -Format 's') + " ===") -Encoding utf8
function W($s) { Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function HX($d) { if ($null -eq $d) { return '' }; return (($d | ForEach-Object { $_.ToString('X2') }) -join '') }

Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs'), (Join-Path $root 'P3.cs')) -ErrorAction Stop
W ("Gx.Open = " + [Gx]::Open())

$stable = 0; $live = 0; $err = 0
for ($hi = 0x00; $hi -le 0xFF; $hi++) {
    $a = $hi * 0x100
    $lg1 = ''; $g2 = ''; $g3 = ''
    $d1 = [Gx]::Read([int]$a, 16, [ref]$lg1)
    Start-Sleep -Milliseconds 180
    $d2 = [Gx]::Read([int]$a, 16, [ref]$lg2)
    Start-Sleep -Milliseconds 180
    $d3 = [Gx]::Read([int]$a, 16, [ref]$lg3)
    $h1 = HX $d1; $h2 = HX $d2; $h3 = HX $d3
    $cls = ''
    if ($h1 -eq '' -or $h2 -eq '' -or $h3 -eq '') { $cls = 'ERR'; $err++ }
    elseif ($h1 -eq $h2 -and $h2 -eq $h3) { $cls = 'STABLE'; $stable++ }
    else { $cls = 'LIVE'; $live++ }
    W ("  0x{0:X4} {1,-7} r1={2} r2={3} r3={4}   [{5}|{6}|{7}]" -f $a, $cls, $h1, $h2, $h3, $lg1, $lg2, $lg3)
}
W ("=== summary: STABLE={0} LIVE={1} ERR={2} ===" -f $stable, $live, $err)
W "=== DONE (read direction only) ==="
