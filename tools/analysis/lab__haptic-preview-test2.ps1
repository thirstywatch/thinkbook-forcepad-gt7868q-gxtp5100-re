# haptic-preview-test2.ps1 -- TEST A, non-interactive version.
#
# Question: at the instant the host WRITES Col02 feature report rid=9 (Haptic
# Intensity), does the touchpad itself emit a short buzz ("preview feedback")?
#
# Channel: Col02 rid=9 ONLY (a HID-declared feature report Windows itself uses).
#          NO Col04. NO vendor reports (rid=6/11/12/13). NO opcode probing.
#
# ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less files as ANSI,
# so non-ASCII here would be mojibake. The user gets instructions in chat.

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log  = Join-Path $here 'haptic-preview-log.txt'

function W($s) {
    Write-Output $s
    Add-Content -Path $log -Value $s -Encoding utf8
}
function Beep($f, $d) { try { [console]::beep($f, $d) } catch {} }

Set-Content -Path $log -Value ("=== preview test2 " + (Get-Date -Format s) + " ===") -Encoding utf8

Add-Type -Path (Join-Path $here 'ColProbe.cs') -ErrorAction Stop

W "--- find Col02 (full-path match, NOT substring) ---"
$path = [ColProbe]::FindPath('&col02')
if (-not $path) { W "FATAL: Col02 not found"; exit 1 }
W ("path = " + $path)

# ---- 1) best-effort read of the current value (backup) ----
$orig = $null
$hr = [ColProbe]::OpenPath($path, $true, $false)
if ($hr -ne [IntPtr]::Zero) {
    $err = 0
    $d = [ColProbe]::GetFeat($hr, 9, 2, [ref]$err)
    if ($d) { $orig = [int]$d[1]; W ("BACKUP rid=9 = " + $orig) }
    else    { W ("BACKUP failed, err=" + $err) }
    [ColProbe]::Close($hr)
} else {
    W "BACKUP: read-only handle refused (expected, PTP driver owns it)"
}

# ---- 2) write-only handle ----
$h = [ColProbe]::OpenPath($path, $false, $true)
if ($h -eq [IntPtr]::Zero) { W "FATAL: write-only handle refused"; exit 1 }
W "write-only handle OK"

# ---- 3) lead-in: give the user time to place a finger ----
W "LEAD-IN 20s -- place a finger lightly on the pad now (do NOT press)"
Beep 600 300
Start-Sleep -Seconds 20

# ---- 4) six writes, 4s apart, each announced by a beep ----
$vals = @(5, 40, 75, 15, 60, 90)
$i = 0
foreach ($v in $vals) {
    $i++
    Beep 1400 70
    $t = (Get-Date).ToString('HH:mm:ss')
    $r = [ColProbe]::SetFeat($h, 9, [byte[]]@($v))
    W ("[{0}] write #{1} val={2} :: {3}" -f $t, $i, $v, $r)
    Start-Sleep -Seconds 4
}

# ---- 5) restore ----
$restore = 10
$src = "project's known-good value"
if ($null -ne $orig) { $restore = $orig; $src = "backed-up original" }
W ("RESTORE rid=9 <- {0} ({1}) :: {2}" -f $restore, $src, [ColProbe]::SetFeat($h, 9, [byte[]]@($restore)))
[ColProbe]::Close($h)

Beep 600 600
W "DONE -- 6 writes delivered, value restored"
