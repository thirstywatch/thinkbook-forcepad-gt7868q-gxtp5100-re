# diff-probe.ps1 -- differential READ-ONLY probe of the Goodix sensor space.
#   -Phase A     finger OFF the pad   -> saves diff-A.bin
#   -Phase B     finger PRESSING hard -> saves diff-B.bin
#   -Phase Diff  compare A vs B (no hardware access)
#
# SAFETY: reads only. No writes. No enumeration. Fixed known-good addresses.
# Total: 13 reads per phase (compare: scan-mem.ps1 did 1093 reads with 0 failures).
param([Parameter(Mandatory=$true)][ValidateSet('A','B','Diff')][string]$Phase)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'diff-probe-log.txt'

function W($s) { $s | Tee-Object -FilePath $LOG -Append | Write-Host }

# windows: base, size  (all previously read without incident)
$WINDOWS = @(
    @(0x5B80, 128),
    @(0x4000, 256),
    @(0x9000, 256)
)

function SaveMap($map, $path) {
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($wnd in $WINDOWS) {
        $b = $map[$wnd[0]]
        $lines.Add(("0x{0:X4} {1}" -f $wnd[0], (($b | ForEach-Object { $_.ToString('X2') }) -join ' ')))
    }
    [IO.File]::WriteAllLines($path, $lines.ToArray())
}

function LoadMap($path) {
    $map = @{}
    foreach ($ln in [IO.File]::ReadAllLines($path)) {
        $sp = $ln.IndexOf(' ')
        if ($sp -lt 3) { continue }
        $base = [Convert]::ToInt32($ln.Substring(2, $sp - 2), 16)
        $bytes = New-Object System.Collections.Generic.List[byte]
        foreach ($t in $ln.Substring($sp + 1).Split(' ')) {
            if ($t.Length -eq 2) { $bytes.Add([Convert]::ToByte($t, 16)) }
        }
        $map[$base] = $bytes.ToArray()
    }
    return $map
}

function DoRead([string]$tag) {
    Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop
    $r = [Gx]::Open()
    W "open: $r"
    if ($r -ne 'ok') { exit 1 }

    # liveness gate: ONE read at a known address, must return data
    $lg = ''
    $probe = [Gx]::Read(0x5B8E, 16, [ref]$lg)
    if ($probe -eq $null) { W "LIVENESS GATE FAILED at 0x5B8E :: $lg -- ABORT"; exit 2 }
    W ("liveness 0x5B8E :: {0} :: {1}" -f $lg, [Gx]::Hex($probe, 16))

    $map = @{}
    $total = 0
    foreach ($wnd in $WINDOWS) {
        $base = $wnd[0]; $size = $wnd[1]
        $acc = New-Object System.Collections.Generic.List[byte]
        $a = $base
        while ($a -lt ($base + $size)) {
            $n = [Math]::Min(60, $base + $size - $a)
            $lg2 = ''
            $d = [Gx]::Read($a, $n, [ref]$lg2)
            if ($d -eq $null -or $d.Length -eq 0) { W ("  [{0}] FAIL at 0x{1:X4} :: {2} -- ABORT" -f $tag,$a,$lg2); exit 3 }
            $acc.AddRange($d)
            W ("  [{0}] 0x{1:X4} +{2} :: {3}" -f $tag, $a, $d.Length, $lg2)
            $a += $d.Length
            Start-Sleep -Milliseconds 10
        }
        $map[$base] = $acc.ToArray()
        $total += $acc.Count
        W ("  [{0}] window 0x{1:X4} = {2} bytes" -f $tag, $base, $acc.Count)
    }
    $out = Join-Path $root ("diff-{0}.txt" -f $tag)
    SaveMap $map $out
    W ("phase {0} done: {1} bytes -> {2}" -f $tag, $total, $out)
}

if ($Phase -eq 'A' -or $Phase -eq 'B') {
    W ("=== diff-probe phase {0} :: {1} ===" -f $Phase, (Get-Date -Format s))
    W "(finger must be OFF for A / PRESSING for B)"
    DoRead $Phase
    exit 0
}

# ---- Diff phase: pure file comparison, no hardware ----
$pa = Join-Path $root 'diff-A.txt'
$pb = Join-Path $root 'diff-B.txt'
if (-not (Test-Path $pa) -or -not (Test-Path $pb)) {
    Write-Host "need both diff-A.txt and diff-B.txt" -ForegroundColor Red
    exit 1
}
# NB: PS variable names are case-INsensitive -- $A and $a are the SAME variable.
# Using $A/$a or $B/$b here silently clobbers the maps. Keep names distinct.
$mapA = LoadMap $pa
$mapB = LoadMap $pb
W ""
W "=== DIFF  (16-bit little-endian words) ==="
foreach ($wnd in $WINDOWS) {
    $base = $wnd[0]
    $arrA = $mapA[$base]; $arrB = $mapB[$base]
    if ($arrA -eq $null -or $arrB -eq $null) { W ("--- window 0x{0:X4}  MISSING in one file, skipped ---" -f $base); continue }
    W ("--- window 0x{0:X4}  ({1} bytes each) ---" -f $base, $arrA.Length)
    $nch = 0
    $maxd = 0; $maxi = -1
    $lim = [Math]::Min($arrA.Length, $arrB.Length) - 1
    for ($i = 0; $i -lt $lim; $i += 2) {
        $va = $arrA[$i] + ($arrA[$i+1] * 256)
        $vb = $arrB[$i] + ($arrB[$i+1] * 256)
        if ($va -ne $vb) {
            $nch++
            $d = $vb - $va
            if ([Math]::Abs($d) -gt $maxd) { $maxd = [Math]::Abs($d); $maxi = $i }
            if ($nch -le 40) { W ("  0x{0:X4}  {1,6} -> {2,6}   d={3,8}" -f ($base+$i), $va, $vb, $d) }
        }
    }
    if ($nch -gt 40) { W ("  ... and {0} more" -f ($nch-40)) }
    W ("  changed cells: {0}" -f $nch)
    if ($maxi -ge 0) { W ("  largest delta: 0x{0:X4}  |d|={1}" -f ($base+$maxi), $maxd) }
}
W "done"
