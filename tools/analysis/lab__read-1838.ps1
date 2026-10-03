# read-1838.ps1 -- STRICTLY READ ONLY. Uses the proven Gx channel (rid=14 OUT/IN on Col04).
#   Only READ frames are sent (Gx.Read -> pkt[5]=0x01). No write frame is issued.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'read-1838-log.txt'
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

W ("=== read 0x1800 / 0x3800 (Gx channel, READ ONLY) :: " + (Get-Date -Format 's') + " ===")
Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop

$r = [Gx]::Open()
W ("Gx.Open = " + $r)
if ($r -ne 'ok') { W "ABORT"; exit 1 }

# CONTROL: known-good address, expect "22 01 1B 00 ..."
$log = ''
$d = [Gx]::Read(0x96F8, 16, [ref]$log)
W ("CONTROL 0x096F8 len=16 :: " + (Hexs $d) + "  [" + (Asc $d) + "]  log=" + $log)
Start-Sleep -Milliseconds 500

foreach ($a in @(0x1800, 0x3800)) {
    foreach ($n in @(4, 8, 16, 27, 32)) {
        $log = ''
        $d = [Gx]::Read($a, $n, [ref]$log)
        if ($d -ne $null -and $d.Length -gt 0) {
            W ("0x{0:X5} len={1,2} :: {2}  [{3}]  log={4}" -f $a, $n, (Hexs $d), (Asc $d), $log)
        } else {
            W ("0x{0:X5} len={1,2} <FAIL>  log={2}" -f $a, $n, $log)
        }
        Start-Sleep -Milliseconds 300
    }
}

W "stability 0x1800 len=16 x3:"
for ($i = 1; $i -le 3; $i++) {
    $log = ''
    $d = [Gx]::Read(0x1800, 16, [ref]$log)
    W ("  #" + $i + " :: " + (Hexs $d))
    Start-Sleep -Milliseconds 300
}
W "=== DONE (READ frames only) ==="
