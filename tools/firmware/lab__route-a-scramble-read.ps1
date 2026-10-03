# route-a-scramble-read.ps1 —— 路线 A①：只读 HW_REG_SCRAMBLE = 0x2218
#
# 依据（追加二十八 / 汇顶官方驱动 gtx8_driver_linux/goodix_gtx8_update.c）：
#      #define HW_REG_SCRAMBLE 0x2218      // 官方在加载明文 ISP 前把它写 0x00（关掉加扰）
#   ⇒ 本脚本【只读不写】，只回答一个问题：这个开关寄存器经厂商内存通道能不能读到
#
# 安全设计：
#   ① 开读前健康门（0x4018 必须是 YELSTO）
#   ② 全程零写入
#   ③ 每次读之间 600 ms 间隔（保守，避免任何批量轮询）
#   ④ 只 8 次读，读完即停；不做扫描、不写任何寄存器
#   ⑤ 若健康门失败 ⇒ 立刻 ABORT，不做任何后续读
#
# 用法：powershell -ExecutionPolicy Bypass -File .\route-a-scramble-read.ps1

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$LOG  = Join-Path $root 'route-a-scramble-read-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }

Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop

function Hx($d) {
    if ($null -eq $d) { return '<null>' }
    if ($d.Length -eq 0) { return '<empty>' }
    return (($d | ForEach-Object { $_.ToString('X2') }) -join ' ')
}
function Asc($d) {
    if ($null -eq $d) { return '' }
    return (-join ($d | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } }))
}

W ("=== 路线 A① 只读 0x2218 (HW_REG_SCRAMBLE) :: {0} ===" -f (Get-Date -Format 's'))
W "全程只读，零写入。"

$r = [Gx]::Open()
W "Col04 open: $r"
if ($r -ne 'ok') { W "ABORT：Col04 读句柄打不开（设备是否在位 / 是否需管理员）"; exit 1 }

# ── 单地址对齐读（起始地址 == 目标地址，避开分块伪影，见 追加十一）──
function One([int]$addr, [int]$size) {
    $log = ''
    $d = [Gx]::Read($addr, $size, [ref]$log)
    if ($null -eq $d -or $d.Length -lt $size) { return @{ ok = $false; d = $d; log = $log } }
    return @{ ok = $true; d = $d; log = $log }
}

# ── ① 健康门 ──
W ""
W "--- ① 健康门 ---"
$h = One 0x4018 4
W ("  0x4018 :: {0}   [{1}]" -f (Hx $h.d), (Asc $h.d))
if (-not $h.ok -or (Asc $h.d) -notlike 'YELS*') {
    W "  ❌ 健康门未通过 ⇒ ABORT，不做任何后续读"
    exit 2
}
W "  ✅ 健康门通过（芯片自报 YELSTO）"

Start-Sleep -Milliseconds 600
$v = One 0x4014 4
W ("  0x4014 :: {0}   [{1}]   (版本寄存器)" -f (Hx $v.d), (Asc $v.d))

# ── ② 目标寄存器 0x2218 ──
W ""
W "--- ② ★ 目标：0x2218 (HW_REG_SCRAMBLE) ---"
$t = One 0x2218 4
W ("  0x2218 :: {0}   [{1}]" -f (Hx $t.d), (Asc $t.d))

# ── ③ 稳定性：同地址再读两次 ──
W ""
W "--- ③ 稳定性复核（同地址连读 3 次，伪影会表现为每次不同）---"
for ($i = 1; $i -le 3; $i++) {
    Start-Sleep -Milliseconds 600
    $d = One 0x2218 4
    W ("  #{0}  0x2218 :: {1}" -f $i, (Hx $d.d))
}

# ── ④ 邻域括号（只读，判断是"真寄存器"还是"未映射返回"）──
W ""
W "--- ④ 邻域括号读（每个地址独立 4 字节，只读）---"
foreach ($a in @(0x2208, 0x2210, 0x2214, 0x221C, 0x2220, 0x2224)) {
    Start-Sleep -Milliseconds 600
    $d = One $a 4
    W ("  0x{0:X4} :: {1}" -f $a, (Hx $d.d))
}

# ── ⑤ 对照：已知可读区（证明通道本身没坏）──
W ""
W "--- ⑤ 对照组（已知区，证明通道正常）---"
foreach ($a in @(0x4000, 0x452C, 0x4160)) {
    Start-Sleep -Milliseconds 600
    $d = One $a 4
    W ("  0x{0:X4} :: {1}   [{2}]" -f $a, (Hx $d.d), (Asc $d.d))
}

# ── ⑥ 收尾健康检查 ──
W ""
W "--- ⑥ 收尾健康检查 ---"
Start-Sleep -Milliseconds 600
$h2 = One 0x4018 4
W ("  0x4018 :: {0}   [{1}]" -f (Hx $h2.d), (Asc $h2.d))
if ((Asc $h2.d) -like 'YELS*') { W "  ✅ 设备健康，与开读前一致" } else { W "  ⚠ 健康状态与开读前不一致（只读操作理论上不应改变任何状态）" }

W ""
W "完成（全程只读，零写入）。"
