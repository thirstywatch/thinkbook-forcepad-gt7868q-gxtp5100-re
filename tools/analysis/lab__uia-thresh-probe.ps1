# uia-thresh-probe.ps1 —— 用 UI Automation 改「触摸板敏感度」→ 差分设备内存，定位阈值落点
#
# 已有事实：
#   · Windows 设置里两个调节项：「点击强度」(Slider 1..4) 与「触摸板敏感度」(ComboBox 4 档)
#   · 注册表 HKCU\...\PrecisionTouchPad 下：FeedbackIntensity=100、ClickForceSensitivity=50
#   · 只改注册表 ⇒ 设备内存 0 变化（不推送）；必须经 UI/驱动下发
#   · 设备侧已知可疑区：0x5B80..0x5C00（0x5B92/0x5B94=48、0x5B96..0x5BE4=70）
#
# 安全：UIA 只改 Windows 设置；设备侧只做 4 字节对齐单块读（不写）。结束自动还原档位。
param([ValidateSet('Snap','SetHigh','SetLow','Diff')][string]$Mode = 'Snap',
      [string]$Tag = 'A')

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$LOG  = Join-Path $here 'uia-thresh-log.txt'
$REG  = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad'
$BASE = 0x5B80; $LEN = 128
function W($s) { $s | Tee-Object -FilePath $LOG -Append | Write-Host }

function GetWin {
    Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes -ErrorAction SilentlyContinue
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $c = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'设置')
    $w = $root.FindFirst([System.Windows.Automation.TreeScope]::Children,$c)
    if(-not $w){ throw '未找到「设置」窗口' }
    return $w
}

function Snap([string]$tag){
    Add-Type -Path @((Join-Path $here 'ColProbe.cs'), (Join-Path $here 'Gx.cs')) -ErrorAction Stop
    $r=[Gx]::Open(); W "Col04 open: $r"; if($r -ne 'ok'){ exit 1 }
    $acc = New-Object System.Collections.Generic.List[byte]
    for($a=$BASE; $a -lt ($BASE+$LEN); $a+=4){
        $lg=''; $d=[Gx]::Read($a,4,[ref]$lg)
        if($null -eq $d -or $d.Length -lt 4){ W "读 0x$($a.ToString('X4')) 失败 :: $lg"; exit 2 }
        $acc.AddRange($d); Start-Sleep -Milliseconds 6
    }
    $out = Join-Path $here ("uia-thresh-$tag.txt")
    [IO.File]::WriteAllBytes($out,$acc.ToArray())
    W ("快照 {0} -> {1}" -f $tag,$out)
    W (($acc | ForEach-Object { $_.ToString('X2') }) -join ' ')
}

function SetSensitivity([string]$want){
    $win = GetWin
    Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes -ErrorAction SilentlyContinue
    # 找 ComboBox「触摸板敏感度」
    $all = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    $cb = $null
    foreach($e in $all){
        if($e.Current.ControlType -eq [System.Windows.Automation.ControlType]::ComboBox -and $e.Current.Name -eq '触摸板敏感度'){ $cb=$e; break }
    }
    if(-not $cb){ W '未找到「触摸板敏感度」下拉框'; return $false }
    # 展开
    try{ $ec=$cb.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern); $ec.Expand(); Start-Sleep -Milliseconds 900 }
    catch{ W ("展开失败: " + $_.Exception.Message) }
    # 在弹出列表里找目标项
    $win2 = GetWin
    $all2 = $win2.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    foreach($e in $all2){
        if($e.Current.Name -eq $want -and $e.Current.ControlType -eq [System.Windows.Automation.ControlType]::ListItem){
            try{
                $si=$e.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern); $si.Select()
                W ("已选择：$want")
                Start-Sleep -Milliseconds 900
                return $true
            }catch{ W ("选择 $want 失败: " + $_.Exception.Message) }
        }
    }
    W "未找到列表项：$want"
    try{ $ec.Collapse() }catch{}
    return $false
}

switch($Mode){
'Snap'    { Snap $Tag }
'SetHigh' { SetSensitivity '最高敏感度' | Out-Null
            W ("注册表 ClickForceSensitivity = " + (Get-ItemProperty $REG).ClickForceSensitivity) }
'SetLow'  { SetSensitivity '低敏感度' | Out-Null
            W ("注册表 ClickForceSensitivity = " + (Get-ItemProperty $REG).ClickForceSensitivity) }
'Diff'    {
    $pa = Join-Path $here 'uia-thresh-A.txt'; $pb = Join-Path $here 'uia-thresh-B.txt'
    if(-not (Test-Path $pa) -or -not (Test-Path $pb)){ W '需要 uia-thresh-A.txt 与 -B.txt'; exit 1 }
    $a=[IO.File]::ReadAllBytes($pa); $b=[IO.File]::ReadAllBytes($pb)
    $n=0
    for($i=0;$i -lt [Math]::Min($a.Length,$b.Length);$i+=2){
        $va=$a[$i] -bor ($a[$i+1] -shl 8); $vb=$b[$i] -bor ($b[$i+1] -shl 8)
        if($va -ne $vb){ $n++; W ("  0x{0:X4}  {1,6} -> {2,6}" -f ($BASE+$i),$va,$vb) }
    }
    W ("变化 {0} 个 16 位单元" -f $n)
}
}
W "done ($Mode $Tag)"
