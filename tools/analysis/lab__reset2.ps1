$ErrorActionPreference = "Continue"
$log = Join-Path $PSScriptRoot "reset-result2.txt"
function W($m){ $m | Out-File -FilePath $log -Append -Encoding utf8 }
W "=== A) restart touchpad device ==="
W (pnputil /restart-device "ACPI\GXTP5100\1" 2>&1 | Out-String)
Start-Sleep -Seconds 6
W "=== B) status ==="
W (pnputil /enum-devices /instanceid "ACPI\GXTP5100\1" 2>&1 | Out-String)
W "=== C) find parent + restart it ==="
try {
  $parent = (Get-PnpDeviceProperty -InstanceId "ACPI\GXTP5100\1" -KeyName "DEVPKEY_Device_Parent" -ErrorAction Stop).Data
  W ("parent = " + $parent)
  W (pnputil /restart-device "$parent" 2>&1 | Out-String)
  Start-Sleep -Seconds 10
} catch { W ("WMI/parent failed: " + $_.Exception.Message) }
W "=== D) final status ==="
W (pnputil /enum-devices /instanceid "ACPI\GXTP5100\1" 2>&1 | Out-String)
W "=== E) all touchpad nodes ==="
W (pnputil /enum-devices 2>&1 | Select-String -Pattern "GXTP5100" -Context 6,4 | Out-String)
