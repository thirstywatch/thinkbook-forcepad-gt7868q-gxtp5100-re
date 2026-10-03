# rw-scan-elevated.ps1 -- runs elevated.  ASCII only.
# Tries to load the RWEverything driver and run the read-only scan script.
# Records everything to rw-run-result.txt so the agent can read it back.
$ErrorActionPreference = 'Continue'

$RWE   = '<LAB>\touchpad-lab\rwe\Win64\Portable\Rw.exe'
$SCAN  = '<LAB>\touchpad-lab\poc\rwe-cmd\00-scan.rw'
$LOG   = '<WORKSPACE>'
$RES   = '<WORKSPACE>'

$r = @()
$r += 'time      : ' + (Get-Date).ToString('s')
$r += 'elevated  : ' + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$r += 'Rw exists : ' + (Test-Path $RWE)
$r += 'script    : ' + (Test-Path $SCAN)
$r += 'log path  : ' + $LOG

if (Test-Path $LOG) { Remove-Item $LOG -Force -ErrorAction SilentlyContinue }

try {
    $p = Start-Process -FilePath $RWE -ArgumentList @(
            ('/Command=' + $SCAN),
            ('/LogFile=' + $LOG),
            '/LogDate', '/LogTime',
            '/Min', '/Nologo'
         ) -PassThru
    $r += 'pid       : ' + $p.Id

    $deadline = (Get-Date).AddSeconds(60)
    $sawLog = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        if ((Test-Path $LOG) -and ((Get-Item $LOG).Length -gt 0)) {
            $sawLog = $true
            Start-Sleep -Milliseconds 2000   # let it finish writing
            break
        }
        if ($p.HasExited) { break }
    }

    $r += 'sawLog    : ' + $sawLog
    $r += 'exited    : ' + $p.HasExited
    if ($p.HasExited) { $r += 'exitcode  : ' + $p.ExitCode }

    Start-Sleep -Milliseconds 500
    if (-not $p.HasExited) {
        try { $p.Kill(); $r += 'action    : killed Rw.exe' } catch { $r += 'action    : kill failed' }
    }
} catch {
    $r += 'EXCEPTION : ' + $_.Exception.Message
}

if (Test-Path $LOG) {
    $r += 'log bytes : ' + (Get-Item $LOG).Length
} else {
    $r += 'log bytes : (no log produced)'
}

# also grab any recent CodeIntegrity / RwDrv load failures
try {
    $ev = Get-WinEvent -FilterHashtable @{ LogName='Microsoft-Windows-CodeIntegrity/Operational'; StartTime=(Get-Date).AddMinutes(-5) } -MaxEvents 6 -ErrorAction Stop
    $r += '--- CodeIntegrity events (last 5 min) ---'
    foreach ($e in $ev) { $r += ('  id=' + $e.Id + ' ' + ($e.Message -replace "`r?`n", ' ').Substring(0, [Math]::Min(200, $e.Message.Length))) }
} catch {
    $r += '--- CodeIntegrity: none / unreadable (' + $_.Exception.Message + ') ---'
}

$r | Set-Content -Path $RES -Encoding UTF8
