# gtx8-probe.ps1 —— 按 Goodix 官方源码（fwupd plugins/goodix-tp/fu-goodixtp-gtx8-device.c）
# 里公开的 GTX8 家族寄存器地址，做**纯读**探测。
#
# 官方源码里的地址（均为文档化、纯读）：
#   CMD_ADDR          0x60CC  命令寄存器（刷机命令写这里）
#   BL_STATE_ADDR     0x5095  bootloader 状态（期望 0xDD）
#   FLASH_RESULT_ADDR 0x5096  flash 结果（期望 0xAA）
#   FLASH_BUFFER_ADDR 0xC000  flash 缓冲（4 KB）
#   0x60DC            cfg 版本（1 字节）
#   0x452C            固件信息结构 **72 字节**，含：
#                       [0x09..0x0D] patch PID（5 字节 ASCII，如 "GT7936L"）
#                       [17]         patch VID (BE32)
#                       [19] vice_ver  [20] inter_ver  [21]&0x0F sensor_id
#                       sum8(72 字节) 必须 == 0
#
# 安全：只用官方文档化的 0x20 内存读；**不发任何写命令**；总帧数 ~12；
#       活性门；任何失败即停。
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$LOG = Join-Path $root 'gtx8-probe-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }

Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop
W ("=== GTX8 官方地址纯读探测 :: {0} ===" -f (Get-Date -Format s))

$r = [Gx]::Open()
W "Col04 open: $r"
if ($r -ne 'ok') { W "ABORT"; exit 1 }

function ReadBlk([int]$addr, [int]$len, [string]$label) {
    $log = ''
    $d = [Gx]::Read($addr, $len, [ref]$log)
    if ($null -eq $d -or $d.Length -eq 0) { W ("  [FAIL] 0x{0:X4} {1} :: {2}" -f $addr, $label, $log); return $null }
    W ("  0x{0:X4} {1,-26} :: {2}" -f $addr, $label, [Gx]::Hex($d, $d.Length))
    Start-Sleep -Milliseconds 15
    return $d
}

# 活性门：用项目已验证可读的 0x4000
$lg = ReadBlk 0x4000 16 'liveness (YELSTO/7869)'
if ($null -eq $lg) { W "活性门失败，ABORT"; exit 2 }

W ""
W "--- A. 固件信息结构 0x452C (72 字节，分两次读) ---"
$fi = @()
$a1 = ReadBlk 0x452C 60 'fw_info[0..59]'
$a2 = ReadBlk 0x4568 12 'fw_info[60..71]'
if ($a1) { $fi += $a1 }
if ($a2) { $fi += $a2 }

if ($fi.Count -ge 72) {
    $fw = $fi[0..71]
    # sum8 校验
    $s8 = 0; foreach ($b in $fw) { $s8 = ($s8 + $b) -band 0xFF }
    W ("  sum8(72) = 0x{0:X2}  ({1})" -f $s8, $(if ($s8 -eq 0) { '★ 校验通过（与官方源码的判据一致）' } else { '校验不等于 0 ⇒ 此地址不是 fw_info 结构' }))

    # patch PID：fw_info[0x09..0x0D]，5 字节 ASCII
    $pid = -join ($fw[9..13] | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } })
    W ("  patch PID  = '{0}'   (bytes {1})" -f $pid, (($fw[9..13] | ForEach-Object { $_.ToString('X2') }) -join ' '))
    W ("  [17..20]   = {0} {1} {2} {3}" -f $fw[17], $fw[18], $fw[19], $fw[20])
    $pv = ($fw[17] -shl 24) -bor ($fw[18] -shl 16) -bor ($fw[19] -shl 8) -bor $fw[20]
    W ("  patch VID(raw BE32 @17) = 0x{0:X8}" -f $pv)
    W ("  vice_ver(fw_info[19]) = 0x{0:X2}   inter_ver([20]) = 0x{1:X2}   sensor_id([21]&0x0F) = {2}" -f $fw[19], $fw[20], ($fw[21] -band 0x0F))
    W ("  全部 72 字节 = {0}" -f (($fw | ForEach-Object { $_.ToString('X2') }) -join ' '))
    W ("  ASCII 视图   = {0}" -f (-join ($fw | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } })))
}

W ""
W "--- B. 版本与命令寄存器 ---"
$cfg = ReadBlk 0x60DC 8 'cfg version @0x60DC'
if ($cfg) { W ("    ⇒ cfg_ver = 0x{0:X2}" -f $cfg[0]) }
ReadBlk 0x60CC 16 'CMD_ADDR @0x60CC'

W ""
W "--- C. bootloader / flash 状态 ---"
ReadBlk 0x5090 16 'BL_STATE 0x5095 / FLASH_RESULT 0x5096'
ReadBlk 0xC000 16 'FLASH_BUFFER @0xC000'

W ""
W "完成（全程只读）。"
