# read-flashmap.ps1 -- STRICTLY READ ONLY (only Gx::Read frames, pkt[5]=0x01).
#   Purpose: probe the 16-bit flash window for regions the UPDATE PACKAGE DOES NOT CONTAIN.
#   Closed-loop control: 0x8000.. is block idx3 (flash_addr 0x08000, 0x2000 B).
#     If device flash == our decrypted plaintext, then dec_data[0x4800 + (addr-0x8000)] must match.
#   Gaps never present in the package (16-bit addressable): 0x02000-0x04000, 0x0E000-0x10000
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'read-flashmap-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function Hexs($d) { if ($null -eq $d) { return '<null>' }; return (($d | ForEach-Object { $_.ToString('X2') }) -join ' ') }

W ("=== flash map read (16-bit window) :: " + (Get-Date -Format 's') + " ===")
Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop
$r = [Gx]::Open()
W ("Gx.Open = " + $r)
if ($r -ne 'ok') { W "ABORT"; exit 1 }

$targets = @(
    @(0x96F8, 'CONTROL config body start (expect 22 01 1B 00 ...)'),
    @(0x8000, 'block3 flash start'),
    @(0x8400, 'block3'),
    @(0x9000, 'block3'),
    @(0x9400, 'block3'),
    @(0x9800, 'block3'),
    @(0x9C00, 'block3'),
    @(0x2000, 'GAP 0x2000-0x4000 (not in package)'),
    @(0x2400, 'GAP'),
    @(0x2800, 'GAP'),
    @(0x2C00, 'GAP'),
    @(0x3000, 'GAP'),
    @(0x3400, 'GAP'),
    @(0x3800, 'GAP'),
    @(0x3C00, 'GAP'),
    @(0xE000, 'GAP 0xE000-0x10000 (not in package)'),
    @(0xE800, 'GAP'),
    @(0xF000, 'GAP'),
    @(0xF800, 'GAP'),
    @(0xC000, 'ISP load addr / block5 flash 0x0C000'),
    @(0xC800, 'block5'),
    @(0xFE00, 'below block0 at 0xFF00'),
    @(0xFF00, 'block0 = ISP flash addr (expect scrambled ISP)')
)

foreach ($t in $targets) {
    $a = $t[0]; $lbl = $t[1]
    $log = ''
    $d = [Gx]::Read($a, 16, [ref]$log)
    $h1 = Hexs $d
    Start-Sleep -Milliseconds 260
    $log2 = ''
    $d2 = [Gx]::Read($a, 16, [ref]$log2)
    $h2 = Hexs $d2
    $same = if ($h1 -eq $h2) { 'STABLE' } else { '*** UNSTABLE ***' }
    W ("0x{0:X5}  {1,-46} :: {2}  [{3}]  ({4})" -f $a, $lbl, $h1, $log, $same)
    if ($same -ne 'STABLE') { W ("          repeat -> " + $h2) }
    Start-Sleep -Milliseconds 260
}
W "=== DONE (READ frames only, no writes) ==="
