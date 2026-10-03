# read-96f8-full.ps1 -- STRICTLY READ ONLY.  (v4: flat, ASCII-only, single handle)
# NOTES / GOTCHAS (both cost me a run today):
#   1) Windows PowerShell 5.1 parses a BOM-less UTF-8 .ps1 as ANSI -> non-ASCII text CORRUPTS the script. Keep ASCII.
#   2) Do NOT open a second Col04 handle while Gx holds one. Use Gx only.
# Only read-direction frames are sent: 0E 20 00 00 05 01 <addr16BE> <size16BE>
# No write command (0x80/0x83/0x7D/0x11/0x12) is ever sent.
# 16-bit address space only. Start address == target address for every read (single-block discipline).
$root = $PSScriptRoot
$LOG  = Join-Path $root 'read-96f8-full-log.txt'
Set-Content -LiteralPath $LOG -Value ("=== v4 :: " + (Get-Date -Format 's') + " ===") -Encoding utf8
function W($s) { Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }

Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs'), (Join-Path $root 'P3.cs')) -ErrorAction Stop
W ("Gx.Open = " + [Gx]::Open())

# ---------- Step 1: length ladder ----------
W ""
W "--- Step 1: length ladder at 0x96F8 ---"
$maxOk = 0
foreach ($sz in @(1, 2, 4, 8, 16, 24, 32, 40, 48, 56, 60, 64)) {
    $lg = ''
    $d = [Gx]::Read(0x96F8, [int]$sz, [ref]$lg)
    $hx = if ($null -eq $d) { '<null>' } else { ($d | ForEach-Object { $_.ToString('X2') }) -join '' }
    W ("  size={0,-3} -> {1}   [{2}]" -f $sz, $hx, $lg)
    if ($lg -notmatch 'fail' -and $lg -notmatch 'recv-fail') { if ($sz -gt $maxOk) { $maxOk = $sz } }
    Start-Sleep -Milliseconds 350
}
W ("  max single-report length = " + $maxOk)
if ($maxOk -lt 8) { W "  !! abort: no usable length"; exit 1 }

# ---------- Step 2: two full sweeps of 1024 B ----------
$CH = $maxOk
W ""
W ("--- sweep A (block=" + $CH + ") --- " + (Get-Date -Format 'HH:mm:ss'))
$hexA = New-Object System.Text.StringBuilder
$addr = 0x96F8
while ($addr -lt 0x96F8 + 1024) {
    $n = [Math]::Min($CH, (0x96F8 + 1024) - $addr)
    $lg = ''
    $d = [Gx]::Read([int]$addr, [int]$n, [ref]$lg)
    $hx = if ($null -eq $d) { '<null>' } else { ($d | ForEach-Object { $_.ToString('X2') }) -join '' }
    [void]$hexA.Append($hx)
    W ("  0x{0:X4} n={1,-3} :: {2}   [{3}]" -f $addr, $n, $hx, $lg)
    $addr = $addr + $n
    Start-Sleep -Milliseconds 280
}
W ""
W "=== PASS A FULL HEX ==="
W $hexA.ToString()

Start-Sleep -Seconds 3
W ""
W ("--- sweep B (block=" + $CH + ") --- " + (Get-Date -Format 'HH:mm:ss'))
$hexB = New-Object System.Text.StringBuilder
$addr = 0x96F8
while ($addr -lt 0x96F8 + 1024) {
    $n = [Math]::Min($CH, (0x96F8 + 1024) - $addr)
    $lg = ''
    $d = [Gx]::Read([int]$addr, [int]$n, [ref]$lg)
    $hx = if ($null -eq $d) { '<null>' } else { ($d | ForEach-Object { $_.ToString('X2') }) -join '' }
    [void]$hexB.Append($hx)
    W ("  0x{0:X4} n={1,-3} :: {2}   [{3}]" -f $addr, $n, $hx, $lg)
    $addr = $addr + $n
    Start-Sleep -Milliseconds 280
}
W ""
W "=== PASS B FULL HEX ==="
W $hexB.ToString()
W ("PASS_A_EQ_PASS_B = " + ($hexA.ToString() -eq $hexB.ToString()))

# ---------- Step 3: control points ----------
W ""
W "--- Step 3: control points ---"
foreach ($a in @(0x8400, 0x8410, 0x9700, 0x9AF8, 0x96F8)) {
    $lg = ''
    $d = [Gx]::Read([int]$a, 16, [ref]$lg)
    $hx = if ($null -eq $d) { '<null>' } else { ($d | ForEach-Object { $_.ToString('X2') }) -join '' }
    W ("  0x{0:X4} :: {1}   [{2}]" -f $a, $hx, $lg)
    Start-Sleep -Milliseconds 300
}
W "=== DONE (read direction only) ==="
