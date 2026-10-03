# vib-link.ps1 —— 发/读分离探针（v2，2026-09-14）
#   用法：
#     .\vib-link.ps1 SEND   <类hex> <子命令hex> "<payload hex>" [dwellMs]   # 只发不读，立刻退出
#     .\vib-link.ps1 LISTEN [每步超时ms]                                     # 只读不发（新进程）
#     .\vib-link.ps1 HEALTH                                                 # 只做体检
#     .\vib-link.ps1 ONE    <in|read|feat|mem> <a1> [a2]                     # ★一个进程只做一次调用
#     .\vib-link.ps1 RUN    <类hex> <子命令hex> "<payload hex>"              # 旧行为：同进程发+读
param(
  [string]$Mode = "HEALTH",
  [string]$P1 = "A1",
  [string]$P2 = "0F",
  [string]$P3 = "18 00 00 1B",
  [int]$P4 = 400,
  [int]$P5 = 1
)
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Add-Type -Path (Join-Path $root "ColProbe.cs"), (Join-Path $root "VibLink.cs")

switch ($Mode.ToUpper()) {
  "SEND"   { $rc = [VibLink]::Send([Convert]::ToInt32($P1,16), [Convert]::ToInt32($P2,16), $P3, $P4, $P5) }
  "LISTEN" { $rc = [VibLink]::Listen([int]$P1) }
  "HEALTH" { $rc = [VibLink]::HealthOnly() }
  "ONE"    { $rc = [VibLink]::One($P1, $P2, $P3) }
  "MEMSCAN" { $rc = [VibLink]::MemScan([Convert]::ToInt32($P1,16), [Convert]::ToInt32($P2,16)) }
  "MEMWATCH" { $rc = [VibLink]::MemWatch([Convert]::ToInt32($P1,16), [Convert]::ToInt32($P2,16), [int]$P3, $P4) }
  "MEMDUMP"  { $rc = [VibLink]::MemDump([Convert]::ToInt32($P1,16), [Convert]::ToInt32($P2,16), $P3) }
  "LADDER"   { $rc = [VibLink]::RateLadder([Convert]::ToInt32($P1,16), [Convert]::ToInt32($P2,16)) }
  "CLICKWATCH" { $rc = [VibLink]::ClickWatch([int]$P1, [int]$P2) }
  "WATCHDUMP" { $rc = [VibLink]::WatchDump([Convert]::ToInt32($P1,16), [int]$P2, [int]$P3) }
  "MEM2"      { $rc = [VibLink]::Mem2Read([Convert]::ToInt64($P1,16), [Convert]::ToInt32($P2,16)) }
  "RUN"    { $rc = [VibLink]::Send([Convert]::ToInt32($P1,16), [Convert]::ToInt32($P2,16), $P3, 0) }
  default  { "未知模式: $Mode"; $rc = 9 }
}
"exit=$rc"
