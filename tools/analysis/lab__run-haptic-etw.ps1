param(
    [int]$Seconds = 25,
    [string]$OutDir = (Join-Path $PSScriptRoot '_etw')
)

$ErrorActionPreference = 'Stop'
$session = 'TP_HAPTIC_TRACE'
$etl = Join-Path $OutDir 'haptic-toggle.etl'
$csv = Join-Path $OutDir 'haptic-toggle.csv'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Remove-Item $etl, $csv -Force -ErrorAction SilentlyContinue

try {
    logman start $session -ets -o $etl `
        -p Microsoft-Windows-Input-HIDCLASS 0x8000000000000000 0x4 | Out-Null
    # logman accepts one -p on start; add the second provider with update.
    logman update $session -ets `
        -p Microsoft-Windows-SPB-HIDI2C 0xC000000000000000 0x4 | Out-Null
    Start-Sleep -Seconds $Seconds
}
finally {
    logman stop $session -ets 2>$null | Out-Null
    if (Test-Path $etl) {
        tracerpt $etl -o $csv -of CSV -y 2>$null | Out-Null
    }
}
Write-Output ("ETL={0}" -f $etl)
Write-Output ("CSV={0}" -f $csv)
