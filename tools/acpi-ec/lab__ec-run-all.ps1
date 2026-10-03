# ec-run-all.ps1 -- ONE-SHOT: EC read-chain selftest, gate, then the 6-phase probe.
# Pure ASCII on purpose (project discipline: PS 5.1 + GBK console).
# Log: _logs\ec-run-all-latest.log (transcript) + timestamped archive copy at end.
# Launch elevated via:  run-ec-all.bat  (right-click -> Run as administrator)
# Exit codes: 10 = not elevated, 11 = script missing, else propagates child codes.

$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
if (-not (Test-Path (Join-Path $here 'ec-selftest.ps1'))) { $here = '<LAB>\touchpad-lab\poc' }
$logs = Join-Path $here '_logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$log = Join-Path $logs 'ec-run-all-latest.log'
$sel = Join-Path $here 'ec-selftest.ps1'
$prb = Join-Path $here 'ec-haptic-probe.ps1'

$adm = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Start-Transcript -Path $log -Force | Out-Null
"EC-ALL: start $(Get-Date -Format s)   admin=$adm" | Write-Host

if (-not $adm) {
    "EC-ALL: NOT-ELEVATED -> stop. Right-click run-ec-all.bat -> Run as administrator." | Write-Host
    Stop-Transcript | Out-Null
    exit 10
}
if (-not (Test-Path -LiteralPath $sel)) { "EC-ALL: ec-selftest.ps1 missing -> stop" | Write-Host; Stop-Transcript | Out-Null; exit 11 }
if (-not (Test-Path -LiteralPath $prb)) { "EC-ALL: ec-haptic-probe.ps1 missing -> stop" | Write-Host; Stop-Transcript | Out-Null; exit 11 }

# Track how long since the last transcript read, so we can tail progress if needed.
"EC-ALL: === stage 1/2  selftest (no action needed, ~20 s) ===" | Write-Host
$sc = $null
& $sel
$sc = $LASTEXITCODE
"EC-ALL: selftest_exit=$sc" | Write-Host

if ($null -ne $sc -and $sc -ne 0) {
    "EC-ALL: SELFTEST FAILED (exit $sc) -> probe NOT started." | Write-Host
    "EC-ALL: send _logs\ec-run-all-latest.log back for analysis." | Write-Host
} else {
    "EC-ALL: === stage 2/2  probe: 6 phases, follow the on-screen prompts (~7-8 min) ===" | Write-Host
    $t0 = Get-Date
    $pc = $null
    try { & $prb; $pc = $LASTEXITCODE } catch { "EC-ALL: probe threw: $($_.Exception.Message)" | Write-Host }
    "EC-ALL: probe_exit=$pc" | Write-Host
    $latest = Join-Path $here 'ec-haptic-latest.txt'
    $ok2 = $false
    if (Test-Path -LiteralPath $latest) { if ((Get-Item -LiteralPath $latest).LastWriteTime -gt $t0.AddSeconds(-1)) { $ok2 = $true } }
    if ($ok2) { "EC-ALL: DONE-OK. result file updated: $latest" | Write-Host }
    else { "EC-ALL: WARNING - ec-haptic-latest.txt NOT updated; probe did not finish. See log." | Write-Host }
}

"EC-ALL: end $(Get-Date -Format s)" | Write-Host
Stop-Transcript | Out-Null
$ts = Join-Path $logs ("ec-run-all-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))
Copy-Item -LiteralPath $log -Destination $ts -Force -ErrorAction SilentlyContinue
