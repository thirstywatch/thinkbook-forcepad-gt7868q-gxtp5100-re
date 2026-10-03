# _p2.ps1 -- STRICTLY READ ONLY. ASCII only. Single handle.
# Question: is a long read at 0x96F8 trustworthy?
# Test A: 4 x 16 B single-block reads at 0x96F8/0x9708/0x9718/0x9728 vs one 64 B read
# Test B: repeat 16 B reads at 0x96F8 and 0x9708 three times, 1 s apart -> stability
# Only read-direction frames (0E 20 00 00 05 01 addr len).
$root = $PSScriptRoot
$LOG  = Join-Path $root '_p2.txt'
Set-Content -LiteralPath $LOG -Value ("=== p2 :: " + (Get-Date -Format 's') + " ===") -Encoding utf8
function W($s) { Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function HX($d) { if ($null -eq $d) { return '<null>' }; return (($d | ForEach-Object { $_.ToString('X2') }) -join '') }

Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs'), (Join-Path $root 'P3.cs')) -ErrorAction Stop
W ("Gx.Open = " + [Gx]::Open())

W ""
W "--- Test A: split 16 B reads vs one 64 B read ---"
$cat = ''
foreach ($a in @(0x96F8, 0x9708, 0x9718, 0x9728)) {
    $lg = ''
    $d = [Gx]::Read([int]$a, 16, [ref]$lg)
    $h = HX $d
    $cat = $cat + $h
    W ("  read 0x{0:X4} 16 -> {1}   [{2}]" -f $a, $h, $lg)
    Start-Sleep -Milliseconds 250
}
W ("  concatenated = " + $cat)
Start-Sleep -Milliseconds 300
$lg = ''
$long = [Gx]::Read(0x96F8, 64, [ref]$lg)
$lh = HX $long
W ("  one 64 B read = " + $lh + "   [" + $lg + "]")
W ("  MATCH_16x4_vs_64 = " + ($cat -eq $lh))

W ""
W "--- Test B: stability of 16 B reads (3 rounds, 1 s apart) ---"
for ($r = 1; $r -le 3; $r++) {
    foreach ($a in @(0x96F8, 0x9708, 0x9718, 0x9728, 0x9738)) {
        $lg = ''
        $d = [Gx]::Read([int]$a, 16, [ref]$lg)
        W ("  r{0} 0x{1:X4} -> {2}   [{3}]" -f $r, $a, (HX $d), $lg)
        Start-Sleep -Milliseconds 150
    }
    Start-Sleep -Seconds 1
}

W ""
W "--- Test C: does a 60 B read at 0x96F8 equal 4 x 15 B reads? ---"
$c2 = ''
foreach ($a in @(0x96F8, 0x9707, 0x9716, 0x9725)) {
    $lg = ''
    $d = [Gx]::Read([int]$a, 15, [ref]$lg)
    $c2 = $c2 + (HX $d)
    Start-Sleep -Milliseconds 250
}
Start-Sleep -Milliseconds 300
$lg = ''
$l60 = [Gx]::Read(0x96F8, 60, [ref]$lg)
W ("  15x4 = " + $c2)
W ("  60B  = " + (HX $l60) + "   [" + $lg + "]")
W ("  MATCH_15x4_vs_60 = " + ($c2 -eq (HX $l60)))
W "=== DONE ==="
