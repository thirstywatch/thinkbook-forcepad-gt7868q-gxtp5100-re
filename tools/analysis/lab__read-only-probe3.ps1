# read-only-probe3.ps1 -- STRICTLY READ ONLY. Issues NO writes to the device.
#   PART 1: descriptor-level value caps for ALL GXTP5100 HID interfaces (metadata only, no device IO)
#   PART 2: FEATURE read attempts (HidD_GetFeature) on Col01..Col04, report err code
#   PART 3: read device addresses 0x1800 / 0x3800 via the Col04 OUT/IN report channel (read only)
# All comments ASCII-only on purpose (PS5.1 + non-BOM encoding issue).

$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'read-only-probe3-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }
function Asc($d) {
    if ($null -eq $d) { return '' }
    $sb = New-Object System.Text.StringBuilder
    foreach ($b in $d) { if ($b -ge 32 -and $b -lt 127) { [void]$sb.Append([char]$b) } else { [void]$sb.Append('.') } }
    return $sb.ToString()
}
function Hexs($d) {
    if ($null -eq $d) { return '<null>' }
    return (($d | ForEach-Object { $_.ToString('X2') }) -join ' ')
}

W ("=== READ-ONLY probe 3 :: " + (Get-Date -Format 's') + " ===")
W ""

try {
    Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs'), (Join-Path $root 'AllCaps.cs')) -ErrorAction Stop
} catch {
    W ("Add-Type FAILED: " + $_.Exception.Message)
    exit 1
}

# ---------- PART 1: descriptor caps (no device IO at all) ----------
W "--- PART 1: descriptor value caps (metadata only) ---"
$paths = [AllCaps]::Paths()
W ("GXTP5100 HID interface count = " + $paths.Count)
foreach ($p in $paths) {
    $brief = $null
    $txt = [AllCaps]::Dump($p, [ref]$brief)
    $short = ($p -replace '.*hid#', '') -replace '#.*', ''
    W ("### " + $short)
    if ($txt) { W $txt } else { W ("  <caps failed: " + $brief + ">") }
    Start-Sleep -Milliseconds 40
}

# ---------- PART 2: FEATURE read attempts ----------
W ""
W "--- PART 2: FEATURE reads (HidD_GetFeature) ---"
$rids = @(1, 3, 6, 7, 9, 11, 12, 13, 14, 15, 16, 32, 35, 43, 44, 45, 46, 47, 48, 49)
foreach ($col in @('Col01', 'Col02', 'Col03', 'Col04')) {
    $h = [ColProbe]::OpenRO($col)
    if ($h -eq [IntPtr]::Zero) { W ("  " + $col + " openRO = FAILED"); continue }
    W ("  " + $col + " openRO = ok")
    $c = [ColProbe]::CapsOf($h)
    if ($c) { W ("    caps: " + ($c -replace "`r?`n", " / ")) }
    $okCount = 0; $failCount = 0
    foreach ($rid in $rids) {
        $err = 0
        $d = [ColProbe]::GetFeat($h, $rid, 65, [ref]$err)
        if ($d -ne $null -and $d.Length -gt 0) {
            W ("    RID=0x{0:X2} OK  len={1} :: {2}  [{3}]" -f $rid, $d.Length, (Hexs $d), (Asc $d))
            $okCount++
        } else {
            $failCount++
            W ("    RID=0x{0:X2} fail err=0x{1:X8}" -f $rid, $err)
        }
        Start-Sleep -Milliseconds 80
    }
    W ("    => ok=" + $okCount + " fail=" + $failCount)
    [ColProbe]::Close($h)
    Start-Sleep -Milliseconds 150
}

# ---------- PART 3: Gx read 0x1800 / 0x3800 (read only) ----------
W ""
W "--- PART 3: read device addr 0x1800 / 0x3800 (read only, NO write) ---"
$r = [Gx]::Open()
W ("  Gx.Open = " + $r)
if ($r -eq 'ok') {
    # liveness control first (known good address)
    $log = ''
    $d = [Gx]::Read(0x96F8, 16, [ref]$log)
    W ("  CONTROL 0x096F8 len=16 :: " + (Hexs $d) + "  [" + (Asc $d) + "]")
    Start-Sleep -Milliseconds 400
    foreach ($a in @(0x1800, 0x3800)) {
        foreach ($n in @(4, 8, 16, 27, 32)) {
            $log = ''
            $d = [Gx]::Read($a, $n, [ref]$log)
            if ($d -ne $null -and $d.Length -gt 0) {
                W ("  0x{0:X5} len={1,2} :: {2}  [{3}]" -f $a, $n, (Hexs $d), (Asc $d))
            } else {
                W ("  0x{0:X5} len={1,2} <FAIL>  log={2}" -f $a, $n, $log)
            }
            Start-Sleep -Milliseconds 400
        }
    }
    # stability: repeat 3x on 0x1800
    W "  stability 0x1800 x3:"
    for ($i = 1; $i -le 3; $i++) {
        $log = ''
        $d = [Gx]::Read(0x1800, 16, [ref]$log)
        W ("    #" + $i + " :: " + (Hexs $d))
        Start-Sleep -Milliseconds 400
    }
} else {
    W "  Gx.Open failed -> skip PART 3"
}

W ""
W "=== DONE. No writes were issued. ==="
