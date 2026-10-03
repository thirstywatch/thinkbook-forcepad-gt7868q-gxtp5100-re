# refresh-test.ps1 -- READ-ONLY measurement of how fast the 0x9000 buffer turns over.
#
# Reads the SAME 60 bytes twice with a controlled gap, and counts changed bytes.
# This tells us the refresh period WITHOUT writing anything: if the buffer changes
# between two reads 10 ms apart, then any value we write is gone before the next
# scan, and "fake pressure by writing the sensor map" is dead.
#
# SAFETY: reads only, single known-good address (0x9000), ~13 reads total.
param()

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop

$ADDR = 0x9000
$LEN  = 60
$GAPS = @(0, 5, 20, 50, 200, 1000)

$r = [Gx]::Open()
if ($r -ne 'ok') { Write-Host "open failed: $r" -ForegroundColor Red; exit 1 }

# liveness gate
$lg = ''
$probe = [Gx]::Read(0x5B8E, 16, [ref]$lg)
if ($probe -eq $null) { Write-Host "LIVENESS GATE FAILED :: $lg -- ABORT" -ForegroundColor Red; exit 2 }
Write-Host ("liveness 0x5B8E :: {0} :: {1}" -f $lg, [Gx]::Hex($probe, 16))
Write-Host ""
Write-Host ("target 0x{0:X4}  len {1}   (READ-ONLY; this measures the buffer's refresh period)" -f $ADDR, $LEN)
Write-Host ""

Write-Host "  gap(ms)  changed/60   first-changed"
foreach ($g in $GAPS) {
    $l1 = ''; $d1 = [Gx]::Read($ADDR, $LEN, [ref]$l1)
    if ($d1 -eq $null) { Write-Host ("  gap {0,5}  FAIL :: {1}" -f $g, $l1) -ForegroundColor Red; exit 3 }
    if ($g -gt 0) { Start-Sleep -Milliseconds $g }
    $l2 = ''; $d2 = [Gx]::Read($ADDR, $LEN, [ref]$l2)
    if ($d2 -eq $null) { Write-Host ("  gap {0,5}  FAIL :: {1}" -f $g, $l2) -ForegroundColor Red; exit 3 }

    $n = 0; $first = -1
    for ($i = 0; $i -lt $LEN; $i++) {
        if ($d1[$i] -ne $d2[$i]) { $n++; if ($first -lt 0) { $first = $i } }
    }
    if ($first -ge 0) {
        Write-Host ("  gap {0,5}   {1,3}/60     0x{2:X4}   {3} -> {4}" -f `
            $g, $n, ($ADDR + $first), $d1[$first].ToString('X2'), $d2[$first].ToString('X2'))
    } else {
        Write-Host ("  gap {0,5}   {1,3}/60     (identical)" -f $g, $n)
    }
    Start-Sleep -Milliseconds 30
}
Write-Host ""
Write-Host "done -- no writes were performed."
