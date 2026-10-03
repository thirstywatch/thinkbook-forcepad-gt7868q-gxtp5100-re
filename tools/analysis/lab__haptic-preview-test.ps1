# haptic-preview-test.ps1  —— 测试 A
#
# 问题：写入 Col02 的 HID 已声明 feature 报表 rid=9（Haptic Intensity）的
#       那一瞬间，触控板会不会自己震一下（"预览反馈"）？
#
# 通道：只碰 Col02 的 rid=9。不碰 Col04，不碰任何厂商报表（rid=6/11/12/13）。
# 形态：前台、交互、10 次事件，全部由你按回车驱动。写前先试读原值备份。
#
# 方法：一半试次是"空操作"（不写任何东西），但顺序不告诉你 —— 盲测。
#       真写入那一组如果有震感、空操作那一组没有，才算成立。

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log  = Join-Path $here 'haptic-preview-log.txt'

function W($s) {
    Write-Host $s
    Add-Content -Path $log -Value $s -Encoding utf8
}

Set-Content -Path $log -Value ("=== haptic preview test " + (Get-Date -Format s) + " ===") -Encoding utf8

Add-Type -Path (Join-Path $here 'ColProbe.cs') -ErrorAction Stop

W "================================================================"
W "  触控板「写入强度时会不会震一下」盲测"
W "  只写 Col02 的 rid=9（HID 声明过的报表）。不碰厂商通道。"
W "  出问题：先关这个窗口；不行按 Fn+F8；再不行关机拔电长按电源键。"
W "================================================================"
W ""
W ("日志：{0}" -f $log)

# --- 集合路径（必须用完整路径匹配，子串会误命中别的设备）---
$path = [ColProbe]::FindPath('&col02')
if (-not $path) { W "找不到 Col02，退出。"; Read-Host "按回车关闭"; exit 1 }
W ("Col02 = {0}" -f $path)
W ""

# --- 1) 先试只读句柄，取原值备份 ---
$orig = $null
$hr = [ColProbe]::OpenPath($path, $true, $false)
if ($hr -ne [IntPtr]::Zero) {
    $err = 0
    $d = [ColProbe]::GetFeat($hr, 9, 2, [ref]$err)
    if ($d) { $orig = [int]$d[1]; W ("[备份] 读到当前 rid=9 = {0}" -f $orig) }
    else    { W ("[备份] 读 rid=9 失败 err={0}" -f $err) }
    [ColProbe]::Close($hr)
} else {
    W "[备份] Col02 只读句柄打不开（被系统独占，预期内）—— 无法备份原值"
}
W ""

# --- 2) 只写句柄 ---
$h = [ColProbe]::OpenPath($path, $false, $true)
if ($h -eq [IntPtr]::Zero) { W "Col02 只写句柄也打不开，退出。"; Read-Host "按回车关闭"; exit 1 }
W "[句柄] Col02 只写句柄 OK"
W ""

# --- 3) 基线 ---
W "【第 1 步 / 基线】"
W "  用一根手指在板上正常点一下，记住现在这个反馈力度。"
W "  （等会儿结束时会回写，目标是让你感觉和现在一样）"
Read-Host "  记住后按回车继续"

# --- 试次表：R = 真写入，S = 空操作（不告诉用户）---
$plan = @('R','S','R','R','S','R','S','R','R','S')
$vals = @(5, 40, 75, 15, 60, 90)   # 6 次真写入，每次都和上次不同
$vi = 0

W ""
W "【第 2 步 / 正式测试】共 $($plan.Count) 个试次，其中**有几次是空的**（不写任何东西）。"
W ""
W "  每个试次这样做："
W "    1) 用一根手指【轻放】在触控板上（别按下去），保持不动"
W "    2) 用另一只手按回车 —— 【回车按下的那一瞬间】就是写入发生的时刻"
W "    3) 立刻回答：那一瞬间，手指下面有没有额外的震感 / 麻感"
W ""
W "  注意：只判断'按回车的那一下'，不要去点板子。"
W ""
Read-Host "  准备好了按回车开始"

$results = @()
for ($i = 0; $i -lt $plan.Count; $i++) {
    $kind = $plan[$i]
    Read-Host ("  ── 试次 {0}/{1}：手指放好，按回车" -f ($i + 1), $plan.Count) | Out-Null
    $t = Get-Date
    $val = $null
    $setr = '(空操作)'
    if ($kind -eq 'R') {
        $val = $vals[$vi]; $vi++
        $setr = [ColProbe]::SetFeat($h, 9, [byte[]]@($val))
    }
    $r = Read-Host "     ↑ 有震感吗？ 有=y / 没有=n"
    if ($r -match '^[yY]') { $ans = 'Y' } else { $ans = 'n' }
    $results += [pscustomobject]@{ n = $i + 1; kind = $kind; val = $val; ans = $ans; t = $t.ToString('HH:mm:ss') }
    W ("     [{0}] {1} val={2} 答={3}" -f ($i + 1), $kind, $(if ($null -eq $val) { '-' } else { $val }), $ans)
    W ("         {0}" -f $setr)
}

# --- 4) 揭盲 + 统计 ---
W ""
W "【第 3 步 / 结果】"
$rY = @($results | Where-Object { $_.kind -eq 'R' -and $_.ans -eq 'Y' }).Count
$rN = @($results | Where-Object { $_.kind -eq 'R' -and $_.ans -eq 'n' }).Count
$sY = @($results | Where-Object { $_.kind -eq 'S' -and $_.ans -eq 'Y' }).Count
$sN = @($results | Where-Object { $_.kind -eq 'S' -and $_.ans -eq 'n' }).Count
W ("  真写入 {0} 次：有震感 {1} / 无 {2}" -f ($rY + $rN), $rY, $rN)
W ("  空操作 {0} 次：有震感 {1} / 无 {2}" -f ($sY + $sN), $sY, $sN)
W ("  解码表：" + (($results | ForEach-Object { "{0}{1}={2}" -f $_.n, $_.kind, $_.ans }) -join '  '))
W ""
if ($rY -gt 0 -and $sY -eq 0) {
    W "  >>> 真写入有、空操作没有 —— 这是【阳性】。"
} elseif ($rY -eq 0 -and $sY -eq 0) {
    W "  >>> 两组都没有震感 —— 没有证据支持'写入会触发震动'。"
} else {
    W "  >>> 两组都有 / 分布不干净 —— 结果不成立，需要进一步设计。"
}

# --- 5) 回写 ---
W ""
$restore = 10
$src = "项目历史记录的'恢复正常'值"
if ($null -ne $orig) { $restore = $orig; $src = "备份到的原值" }
W ("【第 4 步 / 回写】rid=9 <- {0}（{1}）" -f $restore, $src)
W ("  " + [ColProbe]::SetFeat($h, 9, [byte[]]@($restore)))
[ColProbe]::Close($h)

Read-Host "  现在按一下板子，反馈力度和基线一样吗？（不一样就在窗口里告诉我）—— 按回车结束"
W "=== 结束 ==="
Read-Host "按回车关闭窗口"
