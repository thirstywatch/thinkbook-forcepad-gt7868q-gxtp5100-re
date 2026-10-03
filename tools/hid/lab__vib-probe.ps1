# vib-probe.ps1 —— 跑 VibProbe：单发一条扩展类命令（默认 类0xA1 子命令0x0F = 只读 27B@0x1800）
# 用法:  pwsh -File vib-probe.ps1 [类hex] [子命令hex] [payload hex]
param(
  [string]$Cls = "A1",
  [string]$Sub = "0F",
  [string]$Pay = "18 00 00 1B"
)
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Add-Type -Path (Join-Path $root "ColProbe.cs"), (Join-Path $root "VibProbe.cs")
$rc = 0
if ($Cls -eq "SEND") {
  $rc = [VibProbe]::SendOnly([Convert]::ToInt32($Sub,16), [Convert]::ToInt32($Pay,16), "")
} elseif ($Cls -eq "LISTEN") {
  $rc = [VibProbe]::Listen([int]$Sub)
} else {
  $rc = [VibProbe]::Run([Convert]::ToInt32($Cls, 16), [Convert]::ToInt32($Sub, 16), $Pay)
}
"exit=$rc"
