# threshold-probe.ps1 —— 力度阈值定点实验（Col04 OUT + GTX8 正确帧长常量）
#
# 背景（本项目已确认的事实）：
#   · 写入通道：Col04 OUT（65 字节，rid=0x0E）**有效**；Col02 rid=11 **失败(err=87)**
#   · 成败分水岭：hidbuf[4] = data_sz + 5（GTX8 正确值；照搬 BRLB 的 +7 会被丢弃）
#   · 写入**不持久**：重启后恢复（这一点让实验很安全）
#   · 2026-09-13 那次只改了 0x5B96 起的**前 8 个**值（70→25）⇒ 报文级复测：点击阈值**仍是 140–147**（未生效）
#
# 本脚本的假设：0x5B96 起那 40 个 70 是「40 个传感通道/分区」的按下阈值，只改前 8 个没覆盖到；
#              另加 0x5B92/0x5B94 的 2 个 48（松手阈值）。⇒ 本实验把**这 42 个全改**。
#
# 判定方式（客观，不靠手感）：写完后立即跑 press-capture.ps1，再用 re/press-analyze.py 算
#   "byte39.bit0 跳变时的 HID 压力"。基线：按下中位 143 / 松手中位 94。
#
# 安全：备份 → 只改 0x5B92..0x5BE4 → 回读校验 → 随时 -Mode Restore 还原；重启也会恢复。
param([ValidateSet('Backup','Write','Verify','Restore','Status')][string]$Mode = 'Status')

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$LOG  = Join-Path $here 'threshold-probe-log.txt'
$BAK  = Join-Path $here 'threshold-backup.txt'
$BASE = 0x5B80; $LEN = 128
$TARGET_START = 0x5B92          # 42 个值的起点
$TARGET_COUNT = 42              # 2×48 + 40×70
$NEWVAL = 20                    # 改成 20（明显低于"用力按"的压力，但不为 0）

function W($s) { $s | Tee-Object -FilePath $LOG -Append | Write-Host }
Add-Type -Path @((Join-Path $here 'ColProbe.cs'), (Join-Path $here 'Gx.cs'), (Join-Path $here 'WriteHelper.cs')) -ErrorAction Stop

function ReadBlk([int]$addr,[int]$len){
    # ★ 必须用「起始地址 == 目标地址」的 4 字节对齐单块读。
    #   分块拼接会因 hidclass 对该窗口的字节序处理而得到伪影（追加十一 / 本文件实测：
    #   同一次 Gx::Read(0x5B80,128) 偶发返回完全不同的形态）。
    $acc = New-Object System.Collections.Generic.List[byte]
    for($a=$addr; $a -lt ($addr+$len); $a+=4){
        $lg=''; $d=[Gx]::Read($a,4,[ref]$lg)
        if($null -eq $d -or $d.Length -lt 4){ throw "读 0x$($a.ToString('X4')) 失败 :: $lg" }
        $acc.AddRange($d)
        Start-Sleep -Milliseconds 6
    }
    return ,$acc.ToArray()
}
function HexLine($b){ ($b | ForEach-Object { $_.ToString('X2') }) -join ' ' }

switch ($Mode) {

'Status' {
    $r=[Gx]::Open(); W "Col04 open: $r"; if($r -ne 'ok'){ exit 1 }
    $d=ReadBlk $BASE $LEN
    W ("当前 0x{0:X4} 起 {1} 字节：`n{2}" -f $BASE,$d.Length,(HexLine $d))
    W "--- 16 位解码 ---"
    for($i=0;$i -lt $d.Length-1;$i+=2){
        $v=$d[$i] -bor ($d[$i+1] -shl 8)
        W ("  0x{0:X4} = {1,5}" -f ($BASE+$i),$v)
    }
}

'Backup' {
    $r=[Gx]::Open(); W "Col04 open: $r"; if($r -ne 'ok'){ exit 1 }
    $d=ReadBlk $BASE $LEN
    [IO.File]::WriteAllBytes($BAK,$d)
    W ("已备份 0x{0:X4} 起 {1} 字节 -> {2}" -f $BASE,$d.Length,$BAK)
    W (HexLine $d)
}

'Write' {
    if(-not (Test-Path $BAK)){ W "先跑 -Mode Backup"; exit 1 }
    $r=[Gx]::Open(); W "Col04 open: $r"; if($r -ne 'ok'){ exit 1 }
    # 取当前内容，改目标区间，再整段写回（保持其它字节不变）
    $cur=ReadBlk $BASE $LEN
    $off=$TARGET_START-$BASE
    $mod=[byte[]]::new($LEN); [Array]::Copy($cur,$mod,$LEN)
    for($k=0;$k -lt $TARGET_COUNT;$k++){
        $mod[$off + 2*$k]     = [byte]($NEWVAL -band 0xFF)
        $mod[$off + 2*$k + 1] = [byte](($NEWVAL -shr 8) -band 0xFF)
    }
    W ("将写入：起始 0x{0:X4}，{1} 个 16 位值 -> {2}" -f $TARGET_START,$TARGET_COUNT,$NEWVAL)
    $p02=[ColProbe]::FindPath('&col02')
    $h=if($p02){[ColProbe]::OpenPath($p02,$false,$true)}else{[IntPtr]::Zero}
    # 分段（每段 <= 55 字节，GTX8 单包上限）
    $chunk=55
    for($a=0;$a -lt $LEN;$a+=$chunk){
        $n=[Math]::Min($chunk,$LEN-$a)
        $seg=[byte[]]::new($n); [Array]::Copy($mod,$a,$seg,0,$n)
        $res=[GTX8]::Write16($h,($BASE+$a),$seg)
        W ("  [0x{0:X4} +{1}] {2}" -f ($BASE+$a),$n,$res)
        Start-Sleep -Milliseconds 30
    }
    if($h -ne [IntPtr]::Zero){ [ColProbe]::Close($h) }
    Start-Sleep -Milliseconds 100
    $back=ReadBlk $BASE $LEN
    W ("回读：`n{0}" -f (HexLine $back))
    W ("回读目标区：`n{0}" -f (HexLine ($back[$off..($off+2*$TARGET_COUNT-1)])))
}

'Verify' {
    $r=[Gx]::Open(); W "Col04 open: $r"; if($r -ne 'ok'){ exit 1 }
    $d=ReadBlk $BASE $LEN
    $off=$TARGET_START-$BASE
    $ok=$true
    for($k=0;$k -lt $TARGET_COUNT;$k++){
        $v=$d[$off+2*$k] -bor ($d[$off+2*$k+1] -shl 8)
        if($v -ne $NEWVAL){ $ok=$false }
    }
    W ("目标区是否全为 {0}：{1}" -f $NEWVAL,$ok)
    W (HexLine $d)
}

'Restore' {
    if(-not (Test-Path $BAK)){ W "没有备份文件，无法还原"; exit 1 }
    $r=[Gx]::Open(); W "Col04 open: $r"; if($r -ne 'ok'){ exit 1 }
    $d=[IO.File]::ReadAllBytes($BAK)
    if($d.Length -ne $LEN){ W "备份长度异常：$($d.Length)"; exit 1 }
    $p02=[ColProbe]::FindPath('&col02')
    $h=if($p02){[ColProbe]::OpenPath($p02,$false,$true)}else{[IntPtr]::Zero}
    $chunk=55
    for($a=0;$a -lt $LEN;$a+=$chunk){
        $n=[Math]::Min($chunk,$LEN-$a)
        $seg=[byte[]]::new($n); [Array]::Copy($d,$a,$seg,0,$n)
        W ("  [0x{0:X4} +{1}] {2}" -f ($BASE+$a),$n,([GTX8]::Write16($h,($BASE+$a),$seg)))
        Start-Sleep -Milliseconds 30
    }
    if($h -ne [IntPtr]::Zero){ [ColProbe]::Close($h) }
    Start-Sleep -Milliseconds 100
    W ("还原后回读：`n{0}" -f (HexLine (ReadBlk $BASE $LEN)))
}
}
W "done ($Mode)"
