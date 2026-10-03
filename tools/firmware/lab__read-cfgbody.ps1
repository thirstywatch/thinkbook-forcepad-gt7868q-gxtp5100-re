# read-cfgbody.ps1 -- STRICTLY READ ONLY.
#   (a) linear read of the 1024 B config region at 0x96F8, in 256 B chunks, via _I2C_DIRECT_RW (0x20)
#   (b) try the official _READ_CFG command (byte[1] = 0x0a) on 0x96F8  -- read direction flag only
#   (c) re-read 0x9800 to see whether the live region changed
#   ONLY frames with byte[5] == 0x01 are sent. No write command (0x80/0x83/0x7D/0x11/0x12) is ever sent.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'read-cfgbody-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function Hexs($d) { if ($null -eq $d) { return '<null>' }; return (($d | ForEach-Object { $_.ToString('X2') }) -join ' ') }

W ("=== config-body linear read + _READ_CFG probe (READ ONLY) :: " + (Get-Date -Format 's') + " ===")
Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs'), (Join-Path $root 'P3.cs')) -ErrorAction Stop

$r = [Gx]::Open()
W ("Gx.Open = " + $r)
if ($r -ne 'ok') { exit 1 }

# ---- (a) linear 1024 B in 256 B chunks ----
W ""
W "--- (a) linear 0x96F8 + 0x000/100/200/300, 256 B each (0x20) ---"
foreach ($base in @(0x96F8, 0x97F8, 0x98F8, 0x99F8)) {
    $log = ''
    $d = [Gx]::Read($base, 256, [ref]$log)
    $h = Hexs $d
    W ("0x{0:X5} len=256 :: {1}" -f $base, $h)
    W ("            log={0}" -f $log)
    Start-Sleep -Milliseconds 300
}

# ---- (b) official _READ_CFG = 0x0a ----
W ""
W "--- (b) _READ_CFG (byte[1]=0x0a) probes ---"
$p = [ColProbe]::FindPath('Col04')
$h4 = [ColProbe]::OpenPath($p, $true, $true)
if ($h4 -eq [IntPtr]::Zero) { W "  Col04 open FAILED" } else {
    $cases = @(
        @('0a @0x96F8 x16 ', @(0x0E,0x0A,0x00,0x00,0x05,0x01,0x96,0xF8,0x00,0x10)),
        @('0a @0x96F8 x256', @(0x0E,0x0A,0x00,0x00,0x05,0x01,0x96,0xF8,0x01,0x00)),
        @('0a @0x0000 x16 ', @(0x0E,0x0A,0x00,0x00,0x05,0x01,0x00,0x00,0x00,0x10))
    )
    foreach ($c in $cases) {
        $lg = ''
        $d = [P3]::Raw($h4, [byte[]]$c[1], [ref]$lg)
        W ("  {0} -> {1}   ({2})" -f $c[0], (Hexs $d), $lg)
        Start-Sleep -Milliseconds 350
    }
    # ---- (c) live region re-check ----
    W ""
    W "--- (c) live region re-check (0x8400 / 0x9800) ---"
    foreach ($a in @(0x8400, 0x9800)) {
        $lg = ''
        $d = [P3]::Raw($h4, [byte[]]@(0x0E,0x20,0x00,0x00,0x05,0x01,($a -shr 8),($a -band 0xFF),0x00,0x10), [ref]$lg)
        W ("  0x{0:X5} -> {1}   ({2})" -f $a, (Hexs $d), $lg)
        Start-Sleep -Milliseconds 350
    }
    [ColProbe]::Close($h4)
}
W "=== DONE (read direction only) ==="
