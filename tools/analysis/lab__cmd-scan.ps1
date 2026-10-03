# cmd-scan.ps1 —— GT7868Q 命令空间扫描（带健康门 / 危险名单 / 逐条回读）
#
# 依据（全部来自汇顶官方源码 gdix-hid-fw）：
#   CMD_ADDR    0x4160      命令寄存器
#   VER_ADDR    0x4014      版本/型号寄存器（读出来应是 "YELSTO" + "7869"）
#   命令格式    5 字节 { cmd, 0x00, 0x00, 0x00, cmd }
#   接受信号    写完回读 0x4160 == 0x82 表示被固件接受；0xFF 表示空闲
#   官方命令    0x32 切PTP模式 · 0x33 禁坐标上报 · 0x34 启坐标上报
#   危险命令    {0x00,0x10} 切patch · {0x00,0x11} 开始更新 · {0x0E,0x13} 重启  ⇒ 本脚本绝不发
#
# 安全设计：
#   ① 开扫前健康门（0x4014 必须是 YELSTO）
#   ② 每条命令后做健康检查，一旦 0x4014 变了 ⇒ 立刻停止并报告
#   ③ 跳过 0x00、0x0E（危险命令的首字节）
#   ④ 每条命令后回读 0x4160，找 0x82
#   ⑤ 每条之间留观察时间，便于用耳朵/手指察觉马达是否震
#
# 用法：.\cmd-scan.ps1 -Start 0x30 -End 0x3F -PauseMs 1500

param(
    [int]$Start = 0x30,
    [int]$End   = 0x3F,
    [int]$PauseMs = 1500
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogPath  = Join-Path $here 'cmd-scan-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LogPath -Value $s -Encoding utf8 }

Add-Type -Path @((Join-Path $here 'ColProbe.cs'), (Join-Path $here 'Gx.cs'), (Join-Path $here 'WriteHelper.cs')) -ErrorAction Stop

$CMD_ADDR = 0x4160
$VER_ADDR = 0x4014
$DANGER   = @(0x00, 0x0E)     # 危险命令的首字节

function GetBlk([int]$a) {
    $wlog = ''
    $d = [Gx]::Read($a, 4, [ref]$wlog)
    if ($d -and $d.Length -ge 4) { return ,$d }
    return $null
}
function Hx($d) { if ($d) { ($d | ForEach-Object { $_.ToString('X2') }) -join ' ' } else { '<null>' } }

function Test-Health {
    $d = GetBlk $VER_ADDR
    if (-not $d) { return $false }
    # 期望 0x4018..0x401D 出现 "YELS"+"TO"
    $a = GetBlk 0x4018
    if (-not $a) { return $false }
    $s = -join ($a | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } })
    return ($s -like 'YELS*')
}

W ("=== GT7868Q 命令空间扫描 :: {0} ===" -f (Get-Date -Format 's'))
W ("范围 0x{0:X2}..0x{1:X2}  每条间隔 {2} ms" -f $Start, $End, $PauseMs)

$r = [Gx]::Open()
W "Col04(读) open: $r"
if ($r -ne 'ok') { W "ABORT：读句柄打不开"; exit 1 }

# ── 健康门 ──
W ""
W "--- 健康门 ---"
$a = GetBlk 0x4018
W ("  0x4018 = {0}" -f (Hx $a))
if (-not (Test-Health)) { W "  ❌ 健康门未通过（0x4018 不是 YELS...）⇒ ABORT，不进行任何写入"; exit 2 }
W "  ✅ 健康门通过（芯片自报 YELSTO）"

# ── 写句柄（Col04 输出端点）──
$pcol04 = [ColProbe]::FindPath('&col04')
$h = [ColProbe]::OpenRW($pcol04)
if ($h -eq [IntPtr]::Zero) { W "ABORT：Col04 读写句柄打不开"; exit 3 }
W "  ✅ Col04 读写句柄 OK"

W ""
W "  提示：接下来每条命令间隔 $PauseMs ms —— 请把手轻放在触控板上，注意有没有【震动】。"

$results = @()
$abort = $false

for ($op = $Start; $op -le $End; $op++) {
    if ($DANGER -contains $op) {
        W ("  [0x{0:X2}] 跳过（危险名单首字节）" -f $op)
        continue
    }

    $cmd = [byte[]]@($op, 0x00, 0x00, 0x00, $op)
    $pre = GetBlk $CMD_ADDR

    # 用【正确 +5 帧】写（同时走 Col04 OUT；Col02 rid=11 已知 err=87，忽略）
    $wlog = ''
    [void][Gx]::Write($CMD_ADDR, $cmd, [ref]$wlog)

    # 立即连读找 0x82
    $seen = @()
    for ($i = 0; $i -lt 6; $i++) {
        $d = GetBlk $CMD_ADDR
        if ($d) { $seen += $d[0] }
    }
    $acked = ($seen -contains 0x82)

    $ok = Test-Health
    $mark = if ($acked) { '★ 被接受(0x82)' } else { '' }
    W ("  [0x{0:X2}] 写前 {1} | 回读 {2} | {3} {4}" -f `
        $op, (Hx $pre), (($seen | ForEach-Object { $_.ToString('X2') }) -join ','), `
        $(if ($ok) { 'health OK' } else { '★ HEALTH FAIL' }), $mark)

    $results += [pscustomobject]@{ Op = $op; Acked = $acked; Seen = ($seen -join ','); Health = $ok }

    if (-not $ok) {
        W ""
        W "  ❌❌ 健康检查失败 —— 立即停止扫描，不再发送任何命令。"
        W ("     0x4018 = {0}" -f (Hx (GetBlk 0x4018)))
        W ("     0x4014 = {0}" -f (Hx (GetBlk 0x4014)))
        $abort = $true
        break
    }
    Start-Sleep -Milliseconds $PauseMs
}

[ColProbe]::Close($h)

W ""
W "--- 汇总 ---"
$acc = @($results | Where-Object { $_.Acked })
W ("  扫描 {0} 个操作码，其中【被接受(0x82)】的 {1} 个" -f $results.Count, $acc.Count)
if ($acc.Count -gt 0) {
    W "  ★ 被接受的操作码："
    $acc | ForEach-Object { W ("     0x{0:X2}   回读序列 {1}" -f $_.Op, $_.Seen) }
}
if ($abort) { W "  ⚠ 本次因健康检查失败而中止（见上方日志）" }

W ""
W "--- 收尾健康检查 ---"
W ("  0x4014 = {0}" -f (Hx (GetBlk 0x4014)))
W ("  0x4018 = {0}" -f (Hx (GetBlk 0x4018)))
W ("  0x4160 = {0}" -f (Hx (GetBlk 0x4160)))
W "完成。"


