# read-only-probe4.ps1 -- STRICTLY READ ONLY (no data writes, no feature writes).
#  Fixes the collection-selection bug: use FindPath() (which filters to GXTP5100 first)
#  + OpenPath() instead of OpenRO('ColNN') (whose filter argument is a DEVICE filter,
#    so 'Col02' matched intc816&col02, i.e. a non-Goodix device).
#
#  1) caps for each GXTP5100 collection (metadata only)
#  2) FEATURE reads on the collections that actually HAVE feature reports
#  3) READ device addresses 0x1800 / 0x3800 through the pinned GXTP5100 Col04 handle
#     (ONLY READ frames are sent: pkt[5]=0x01. No write frame is ever sent.)
# ASCII-only source on purpose (PS5.1 non-BOM encoding).

$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'read-only-probe4-log.txt'
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

W ("=== READ-ONLY probe 4 :: " + (Get-Date -Format 's') + " ===")
W ""

try {
    Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'P2.cs')) -ErrorAction Stop
} catch {
    W ("Add-Type FAILED: " + $_.Exception.Message); exit 1
}

# ---- locate the exact GXTP5100 collections ----
W "--- resolved GXTP5100 collection paths (FindPath filters to GXTP5100 first) ---"
$cols = @()
foreach ($c in @('Col01','Col02','Col03','Col04')) {
    $p = [ColProbe]::FindPath($c)
    if ($p) {
        $short = ($p -replace '.*hid#','') -replace '#.*',''
        W ("  " + $c + " -> " + $short)
        $cols += [pscustomobject]@{ Name = $c; Path = $p }
    } else { W ("  " + $c + " -> NOT FOUND") }
}
W ""

# ---- PART 2: FEATURE reads on the REAL Goodix collections ----
W "--- PART 2: FEATURE reads (HidD_GetFeature), read-only ---"
foreach ($c in $cols) {
    $h = [ColProbe]::OpenPath($c.Path, $true, $false)
    if ($h -eq [IntPtr]::Zero) { W ("  " + $c.Name + " openRO FAILED"); continue }
    W ("  " + $c.Name + " openRO ok")
    $cap = [ColProbe]::CapsOf($h)
    if ($cap) { W ("    caps: " + ($cap -replace "`r?`n"," / ")) }
    foreach ($rid in @(2, 3, 6, 9, 11, 12, 13, 14, 35)) {
        $err = 0
        # length guesses: try the collection's max feature length
        foreach ($len in @(65, 66, 257, 737)) {
            $d = [ColProbe]::GetFeat($h, $rid, $len, [ref]$err)
            if ($d -ne $null -and $d.Length -gt 0) {
                W ("    RID=0x{0:X2} reqlen={1} OK :: {2}  [{3}]" -f $rid, $len, (Hexs $d), (Asc $d))
                break
            }
        }
        if ($d -eq $null -or $d.Length -le 0) { W ("    RID=0x{0:X2} fail err=0x{1:X8}" -f $rid, $err) }
        Start-Sleep -Milliseconds 90
    }
    [ColProbe]::Close($h)
    Start-Sleep -Milliseconds 120
}

# ---- PART 3: READ 0x1800 / 0x3800 via pinned Col04 (READ FRAMES ONLY) ----
W ""
W "--- PART 3: device address reads via pinned GXTP5100 Col04 (READ-ONLY) ---"
$p4 = ($cols | Where-Object { $_.Name -eq 'Col04' }).Path
if (-not $p4) { W "  no Col04 path"; }
else {
    $h4 = [ColProbe]::OpenPath($p4, $true, $true)   # write access needed to SEND the read-command frame
    if ($h4 -eq [IntPtr]::Zero) {
        W "  Col04 open(RW) FAILED -- trying RO"
        $h4 = [ColProbe]::OpenPath($p4, $true, $false)
    }
    if ($h4 -eq [IntPtr]::Zero) { W "  Col04 open FAILED, skip PART 3" }
    else {
        W "  Col04 opened (only READ frames will be sent)"
        $log = ''
        $d = [P2]::Read($h4, 0x96F8, 16, [ref]$log)   # CONTROL: known answer 22 01 1B 00 ...
        W ("  CONTROL 0x096F8 len=16 :: " + (Hexs $d) + "  [" + (Asc $d) + "]  log=" + $log)
        Start-Sleep -Milliseconds 400

        foreach ($a in @(0x1800, 0x3800)) {
            foreach ($n in @(4, 8, 16, 27, 32)) {
                $log = ''
                $d = [P2]::Read($h4, $a, $n, [ref]$log)
                if ($d -ne $null -and $d.Length -gt 0) {
                    W ("  0x{0:X5} len={1,2} :: {2}  [{3}]  log={4}" -f $a, $n, (Hexs $d), (Asc $d), $log)
                } else {
                    W ("  0x{0:X5} len={1,2} <FAIL>  log={2}" -f $a, $n, $log)
                }
                Start-Sleep -Milliseconds 350
            }
        }

        W "  stability 0x1800 (len 16) x3:"
        for ($i = 1; $i -le 3; $i++) {
            $log = ''
            $d = [P2]::Read($h4, 0x1800, 16, [ref]$log)
            W ("    #" + $i + " :: " + (Hexs $d))
            Start-Sleep -Milliseconds 350
        }
        [ColProbe]::Close($h4)
    }
}

W ""
W "=== DONE. Only READ/GET frames were issued; no write frame, no feature write. ==="
