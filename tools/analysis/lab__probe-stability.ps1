# _p3.ps1 -- STRICTLY READ ONLY. ASCII only. Single handle.
# Controlled stability test. Addresses are CYCLED (never the same address twice in a row)
# because back-to-back identical requests appear unreliable on this device.
#   0x4014  fw_info (expected stable)
#   0x96F8  cfg header +0x00..0x0F (expected stable, 32 B)
#   0x9708  0x96F8 +0x10 (expected stable)
#   0x9718  0x96F8 +0x20 (SUSPECT: unstable)
#   0x9728  0x96F8 +0x30 (SUSPECT)
#   0x9738  0x96F8 +0x40 (SUSPECT)
#   0x8400  known live region
# 5 rounds, one read per address per round, 300 ms apart.
$root = $PSScriptRoot
$LOG  = Join-Path $root '_p3.txt'
Set-Content -LiteralPath $LOG -Value ("=== p3 :: " + (Get-Date -Format 's') + " ===") -Encoding utf8
function W($s) { Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function HX($d) { if ($null -eq $d) { return '<null>' }; return (($d | ForEach-Object { $_.ToString('X2') }) -join '') }

Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs'), (Join-Path $root 'P3.cs')) -ErrorAction Stop
W ("Gx.Open = " + [Gx]::Open())

$addrs = @(0x4014, 0x96F8, 0x9708, 0x9718, 0x9728, 0x9738, 0x8400)
$hist = @{}
foreach ($a in $addrs) { $hist[$a] = @() }

for ($r = 1; $r -le 5; $r++) {
    W ""
    W ("--- round " + $r + " ---")
    foreach ($a in $addrs) {
        $lg = ''
        $d = [Gx]::Read([int]$a, 16, [ref]$lg)
        $h = HX $d
        $hist[$a] += $h
        W ("  0x{0:X4} -> {1}   [{2}]" -f $a, $h, $lg)
        Start-Sleep -Milliseconds 300
    }
}

W ""
W "--- per-address verdict (5 samples) ---"
foreach ($a in $addrs) {
    $u = ($hist[$a] | Select-Object -Unique)
    $v = if ($u.Count -eq 1) { 'STABLE' } else { ('LIVE (' + $u.Count + ' distinct)') }
    W ("  0x{0:X4} {1}" -f $a, $v)
    foreach ($x in $u) { W ("      " + $x) }
}
W "=== DONE ==="
