# rw-launch.ps1 -- launch Rw.exe ELEVATED with a script, then return immediately.
# ASCII only.  Reads its two parameters from rw-run.txt:
#   line 1 = full path to the .rw command script
#   line 2 = full path for the Rw log file
# Writes rw-launch-status.txt right away (does not wait for Rw to finish).

$HERE = '<WORKSPACE>'
$CFG  = Join-Path $HERE 'rw-run.txt'
$RES  = Join-Path $HERE 'rw-launch-status.txt'
$RWE  = '<LAB>\touchpad-lab\rwe\Win64\Portable\Rw.exe'

$r = @()
$r += 'time = ' + (Get-Date).ToString('s')

if (-not (Test-Path $CFG)) { $r += 'ERROR: rw-run.txt missing'; $r | Set-Content $RES -Encoding UTF8; return }
$cfg = Get-Content $CFG
$script = $cfg[0].Trim()
$log    = $cfg[1].Trim()
$r += 'script = ' + $script
$r += 'log    = ' + $log
$r += 'exists = ' + (Test-Path $script)

if (Test-Path $log) { Remove-Item $log -Force -ErrorAction SilentlyContinue }

try {
    $p = Start-Process -FilePath $RWE -ArgumentList @(
            ('/Command=' + $script),
            ('/LogFile=' + $log),
            '/LogDate', '/LogTime', '/Min', '/Nologo'
         ) -Verb RunAs -PassThru
    $r += 'launched pid = ' + $p.Id
} catch {
    $r += 'LAUNCH FAILED: ' + $_.Exception.Message
}

$r | Set-Content -Path $RES -Encoding UTF8
