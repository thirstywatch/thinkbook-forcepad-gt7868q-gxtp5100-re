param(
  [int]$From = 0,
  [int]$To   = 127,
  [int]$WaitMs = 400
)
$ErrorActionPreference = 'Continue'
Add-Type -Path @("$PSScriptRoot\ColProbe.cs","$PSScriptRoot\Gx.cs","$PSScriptRoot\WriteHelper.cs") -ErrorAction Stop

# 跳过: 0x10/0x11(切patch/开始更新) 0x12(load flash) 0x13(软复位,会重启IC) 0x20(内存读写)
$skip = @(0x10,0x11,0x12,0x13,0x20)
$log  = Join-Path $PSScriptRoot 'opcode-sweep-log.txt'
function W([string]$m){ $m | Out-File -FilePath $log -Append -Encoding utf8 }

$sw = [Diagnostics.Stopwatch]::StartNew()
W ("=== sweep {0:X2}..{1:X2}  wait={2}ms  start {3} ===" -f $From,$To,$WaitMs,(Get-Date -Format 'HH:mm:ss'))

# --- 初始活性确认: 不发任何扫描命令前先确认 IC 活着 ---
$live = [CmdProbe]::ProbeReadMem(0x0000,16,$WaitMs)
W ("[{0,7:N2}s] LIVENESS(init): {1}" -f $sw.Elapsed.TotalSeconds,$live)
if($live -notmatch 'st=0'){
  Write-Output "ABORT: IC 初始就不应答, 未发送任何扫描命令 -> $live"
  exit 2
}

$okCount = 0; $failCount = 0; $interesting = @()
for($op = $From; $op -le $To; $op++){
  if($skip -contains $op){ continue }

  if($op % 16 -eq 0){
    try { [console]::beep(1200,120) } catch {}
    Start-Sleep -Milliseconds 80
    $l = [CmdProbe]::ProbeReadMem(0x0000,16,$WaitMs)
    W ("[{0,7:N2}s] LIVENESS before 0x{1:X2}: {2}" -f $sw.Elapsed.TotalSeconds,$op,$l)
    if($l -notmatch 'st=0'){
      Write-Output ("ABORT: 0x{0:X2} 之前 IC 不再应答 -> {1}" -f $op,$l)
      W ("ABORT at 0x{0:X2}" -f $op)
      exit 3
    }
  }

  $p = New-Object byte[] 65
  $p[0] = 0x0E; $p[1] = [byte]$op; $p[4] = 0x01; $p[5] = 0x01
  $r = [CmdProbe]::SendAndReadBig($p,$WaitMs)
  $t = $sw.Elapsed.TotalSeconds

  if($r -match 'big24'){
    $okCount++
    $hex = ([regex]::Match($r,'big24\[(.*?)\]')).Groups[1].Value
    W ("[{0,7:N2}s] op=0x{1:X2}  OK   {2}" -f $t,$op,$hex)
    $interesting += ("0x{0:X2}  {1}" -f $op,$hex)
  } else {
    $failCount++
    W ("[{0,7:N2}s] op=0x{1:X2}  FAIL {2}" -f $t,$op,$r)
  }
}
$sw.Stop()
$final = [CmdProbe]::ProbeReadMem(0x0000,16,$WaitMs)
W ("FINAL LIVENESS: {0}" -f $final)
W ("SUMMARY: ok={0} fail={1} elapsed={2:N1}s" -f $okCount,$failCount,$sw.Elapsed.TotalSeconds)

Write-Output ("=== scan {0:X2}..{1:X2} done: OK {2} / FAIL {3} / {4:N0}s ===" -f $From,$To,$okCount,$failCount,$sw.Elapsed.TotalSeconds)
Write-Output ("FINAL LIVENESS: " + $final)
Write-Output "--- opcodes that answered ---"
$interesting | ForEach-Object { Write-Output ("  " + $_) }
Write-Output ("log: " + $log)
