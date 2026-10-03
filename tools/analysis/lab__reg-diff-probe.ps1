# reg-diff-probe.ps1 —— 改 Windows 触控板设置 → 差分设备内存，定位「力度阈值 / 震动强度」写到哪
#
# 思路：`ClickForceSensitivity` / `FeedbackIntensity` 是微软 inbox HID 驱动（input.inf）用的值，
#       它必然通过某条 HID feature report 下发到设备。改注册表后差分设备内存，就能找到落点。
#
# 安全：只改 HKCU 下两个 DWORD（会话结束会还原）；设备侧只做 4 字节对齐单块读（不写）。
param([ValidateSet('Snap','Apply','Restore','Diff')][string]$Mode = 'Snap',
      [string]$Tag = 'A')

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$LOG  = Join-Path $here 'reg-diff-log.txt'
$REG  = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad'
function W($s) { $s | Tee-Object -FilePath $LOG -Append | Write-Host }

# 观测区：已知的阈值/配置区，128 字节（32 次 4 字节读）
$BASE = 0x5B80; $LEN = 128

function Snap([string]$tag) {
    Add-Type -Path @((Join-Path $here 'ColProbe.cs'), (Join-Path $here 'Gx.cs')) -ErrorAction Stop
    $r = [Gx]::Open(); W "Col04 open: $r"; if ($r -ne 'ok') { exit 1 }
    $acc = New-Object System.Collections.Generic.List[byte]
    for ($a = $BASE; $a -lt ($BASE + $LEN); $a += 4) {
        $lg = ''; $d = [Gx]::Read($a, 4, [ref]$lg)
        if ($null -eq $d -or $d.Length -lt 4) { W "读 0x$($a.ToString('X4')) 失败 :: $lg"; exit 2 }
        $acc.AddRange($d); Start-Sleep -Milliseconds 6
    }
    $out = Join-Path $here ("reg-diff-$tag.txt")
    [IO.File]::WriteAllBytes($out, $acc.ToArray())
    W ("快照 {0}: 0x{1:X4} 起 {2} 字节 -> {3}" -f $tag, $BASE, $acc.Count, $out)
    W (($acc | ForEach-Object { $_.ToString('X2') }) -join ' ')
}

switch ($Mode) {
'Snap' { Snap $Tag }

'Apply' {
    $before = Get-ItemProperty $REG
    W ("改前：ClickForceSensitivity={0}  FeedbackIntensity={1}  FeedbackEnabled={2}" -f `
        $before.ClickForceSensitivity, $before.FeedbackIntensity, $before.FeedbackEnabled)
    # 备份到文件，便于 Restore
    @{ ClickForceSensitivity = $before.ClickForceSensitivity
       FeedbackIntensity     = $before.FeedbackIntensity } |
        ConvertTo-Json | Set-Content (Join-Path $here 'reg-diff-backup.json') -Encoding utf8
    # 推到极端值（最灵敏方向）
    Set-ItemProperty $REG -Name ClickForceSensitivity -Value 0  -Type DWord
    Set-ItemProperty $REG -Name FeedbackIntensity     -Value 0  -Type DWord
    Start-Sleep -Milliseconds 500
    $after = Get-ItemProperty $REG
    W ("改后：ClickForceSensitivity={0}  FeedbackIntensity={1}" -f $after.ClickForceSensitivity, $after.FeedbackIntensity)
    W "（已备份原值到 reg-diff-backup.json；用 -Mode Restore 还原）"
}

'Restore' {
    $bak = Join-Path $here 'reg-diff-backup.json'
    if (-not (Test-Path $bak)) { W "没有备份文件"; exit 1 }
    $o = Get-Content $bak -Raw | ConvertFrom-Json
    Set-ItemProperty $REG -Name ClickForceSensitivity -Value ([int]$o.ClickForceSensitivity) -Type DWord
    Set-ItemProperty $REG -Name FeedbackIntensity     -Value ([int]$o.FeedbackIntensity)     -Type DWord
    $n = Get-ItemProperty $REG
    W ("已还原：ClickForceSensitivity={0}  FeedbackIntensity={1}" -f $n.ClickForceSensitivity, $n.FeedbackIntensity)
}

'Diff' {
    $pa = Join-Path $here 'reg-diff-A.txt'; $pb = Join-Path $here 'reg-diff-B.txt'
    if (-not (Test-Path $pa) -or -not (Test-Path $pb)) { W "需要 reg-diff-A.txt 与 reg-diff-B.txt"; exit 1 }
    $a = [IO.File]::ReadAllBytes($pa); $b = [IO.File]::ReadAllBytes($pb)
    W ("A={0} B={1} 字节" -f $a.Length, $b.Length)
    $n = 0
    for ($i = 0; $i -lt [Math]::Min($a.Length, $b.Length); $i += 2) {
        $va = $a[$i] -bor ($a[$i+1] -shl 8); $vb = $b[$i] -bor ($b[$i+1] -shl 8)
        if ($va -ne $vb) { $n++; W ("  0x{0:X4}  {1,6} -> {2,6}" -f ($BASE + $i), $va, $vb) }
    }
    W ("变化 {0} 个 16 位单元 / {1}" -f $n, ([Math]::Floor([Math]::Min($a.Length,$b.Length)/2)))
}
}
W "done ($Mode $Tag)"
