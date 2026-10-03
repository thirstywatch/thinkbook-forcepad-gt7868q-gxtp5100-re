# admin-col02-test.ps1  (ASCII only - safe for Windows PowerShell 5.1)
# Usage (must run as Administrator):
#   powershell -ExecutionPolicy Bypass -File "<LAB>\touchpad-lab\poc\admin-col02-test.ps1"
#
# Flow: disable Col03 (mtconfig) -> immediately test Col02 RW + vendor feature reports
#       -> write haptic intensity rid=9 -> send vendor cmd via rid=11 -> re-enable Col03
# Do NOT press F8 while this runs (F8 depends on Col03).
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'col02-test-log.txt'
$inst = 'HID\GXTP5100&Col03\5&52a7aed&0&0002'

function Say($s) { Write-Output $s; Add-Content -Path $log -Value $s -Encoding utf8 }
Set-Content -Path $log -Value ("=== Col02 feature channel test " + (Get-Date -Format s) + " ===") -Encoding utf8

Say "1) disable Col03 (MTConfig)"
$r = pnputil /disable-device $inst 2>&1 | Out-String
Say ("   " + ($r.Trim() -replace "`r?`n", ' | '))
Start-Sleep -Milliseconds 900

try {
    Add-Type -Path (Join-Path $here 'ColProbe.cs') -ErrorAction Stop
    Say "2) collections now present:"
    foreach ($p in [ColProbe]::EnumPaths('GXTP5100')) { Say ("   " + ($p -split '#')[1]) }

    Say "3) try to open Col02 (up to 12 tries x 300ms)"
    $h = [IntPtr]::Zero
    for ($i = 0; $i -lt 12; $i++) {
        $h = [ColProbe]::OpenRW('Col02')
        if ($h -eq [IntPtr]::Zero) { $h = [ColProbe]::OpenRO('Col02') }
        if ($h -ne [IntPtr]::Zero) { Say ("   success on try #" + ($i + 1) + " handle=" + $h); break }
        Start-Sleep -Milliseconds 300
    }
    if ($h -eq [IntPtr]::Zero) { Say "   all 12 tries failed" }

    if ($h -ne [IntPtr]::Zero) {
        Say ("   caps: " + [ColProbe]::CapsOf($h))
        Say "   (PTP collection expected: up=0x000D u=0x0005 in=40 feat=737)"

        Say "4) read feature reports"
        foreach ($t in @(@(9, 2), @(2, 2), @(13, 5), @(11, 67), @(6, 257), @(12, 737))) {
            $err = 0
            $d = [ColProbe]::GetFeat($h, $t[0], $t[1], [ref]$err)
            if ($d) {
                $n = [Math]::Min(24, $d.Length - 1)
                Say ("   rid=" + $t[0] + " len=" + $t[1] + " OK : " + (($d[0..$n] | ForEach-Object { $_.ToString('X2') }) -join ' '))
            }
            else { Say ("   rid=" + $t[0] + " len=" + $t[1] + " FAIL err=" + $err) }
        }

        Say "5) write haptic intensity rid=9 = 100, then read back"
        Say ("   " + [ColProbe]::SetFeat($h, 9, @(100)))
        Start-Sleep -Milliseconds 250
        $err = 0
        $d = [ColProbe]::GetFeat($h, 9, 2, [ref]$err)
        if ($d) { Say ("   readback rid=9: " + (($d | ForEach-Object { $_.ToString('X2') }) -join ' ')) }
        else { Say ("   readback FAILED err=" + $err) }

        Say "6) vendor command via rid=11 (read 4 bytes at 0x60CC)"
        $p = New-Object byte[] 66
        $p[0] = 0x0E; $p[1] = 0x20; $p[4] = 0x05; $p[5] = 0x01
        $p[6] = 0x60; $p[7] = 0xCC; $p[8] = 0x00; $p[9] = 0x04
        Say ("   send: " + [ColProbe]::SetFeat($h, 11, $p))
        Start-Sleep -Milliseconds 200
        $err = 0
        $d = [ColProbe]::GetFeat($h, 11, 67, [ref]$err)
        if ($d) { Say ("   response: " + (($d[0..20] | ForEach-Object { $_.ToString('X2') }) -join ' ')) }
        else { Say ("   read response FAILED err=" + $err) }
        [ColProbe]::Close($h)
    }
    else { Say "   Col02 not openable, skipping tests" }
}
catch { Say ("EXCEPTION: " + $_.Exception.Message) }
finally {
    Say "7) re-enable Col03"
    $r2 = pnputil /enable-device $inst 2>&1 | Out-String
    Say ("   " + ($r2.Trim() -replace "`r?`n", ' | '))
    Say "done. If gestures are broken, press F8 or run: pnputil /restart-device ""ACPI\GXTP5100\1"""
}
