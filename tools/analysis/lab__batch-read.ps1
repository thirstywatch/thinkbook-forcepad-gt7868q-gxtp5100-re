# batch-read.ps1 -- STRICTLY READ ONLY. Reads a small group of addresses (Gx::Read only).
#   -Group A : block3 (in package) + controls          9 reads
#   -Group B : GAP 0x2000-0x4000 (NOT in package)      9 reads
#   -Group C : GAP 0xE000-0x10000 (NOT in package)     9 reads
param([string]$Group = 'A')
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$LOG  = Join-Path $root ("batch-read-" + $Group + "-log.txt")
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function Hexs($d) { if ($null -eq $d) { return '<null>' }; return (($d | ForEach-Object { $_.ToString('X2') }) -join ' ') }

$sets = @{
    'A' = @(0x96F8, 0x8000, 0x8400, 0x9000, 0x9400, 0x9800, 0x9C00, 0xC000, 0xFF00)
    'B' = @(0x2000, 0x2400, 0x2800, 0x2C00, 0x3000, 0x3400, 0x3800, 0x3C00, 0x1E00)
    'C' = @(0xE000, 0xE400, 0xE800, 0xEC00, 0xF000, 0xF400, 0xF800, 0xFC00, 0xDE00)
}
$list = $sets[$Group]
Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop
$r = [Gx]::Open()
W ("=== batch-read group " + $Group + " :: " + (Get-Date -Format 's') + " :: Gx.Open=" + $r + " ===")
if ($r -ne 'ok') { exit 1 }
foreach ($a in $list) {
    $log = ''
    $d = [Gx]::Read($a, 16, [ref]$log)
    $h1 = Hexs $d
    Start-Sleep -Milliseconds 220
    $log2 = ''
    $d2 = [Gx]::Read($a, 16, [ref]$log2)
    $h2 = Hexs $d2
    $st = if ($h1 -eq $h2) { 'STABLE' } else { 'UNSTABLE' }
    W ("0x{0:X5} :: {1}  [{2}] {3}" -f $a, $h1, $log, $st)
    if ($st -eq 'UNSTABLE') { W ("          rep :: " + $h2) }
    Start-Sleep -Milliseconds 220
}
W "=== END group " + $Group + " (read only) ==="
