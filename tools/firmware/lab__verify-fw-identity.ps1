# verify-fw-identity.ps1 —— 用 Col04 class 0x20 的 **32 位地址读**，验证
#   "本地 TF100A 明文镜像 = 设备实际在跑的固件"（PREFLIGHT-STATE §1 标注为从未验证的前提）
#
# 判据：设备 0x08005000 处的前 16 字节，应等于本地容器
#       touchpad_GT7868Q_fw.bin 偏移 0x19ABC 起的明文段头（= 向量表）
#       期望: C8 76 00 20 65 51 00 08 79 A6 00 08 95 88 00 08
#
# 纪律（照项目红线）：单发、前台、间隔 ≥700ms、每次读前后做活性体检、失败立即停手。
# 只读，不写任何数据。
$ErrorActionPreference = 'Continue'
Add-Type -Path @("$PSScriptRoot\ColProbe.cs", "$PSScriptRoot\Gx.cs") -ErrorAction Stop

$log = Join-Path $PSScriptRoot 'fw-identity-log.txt'
function W([string]$m) { $m | Tee-Object -FilePath $log -Append | Out-Null; Write-Output $m }
function Hex($d) { if ($d) { ($d | ForEach-Object { $_.ToString('X2') }) -join ' ' } else { '(null)' } }

W "=== fw identity probe start $(Get-Date -Format s) ==="
W "期望(0x08005000,16): C8 76 00 20 65 51 00 08 79 A6 00 08 95 88 00 08"

$r = [Gx]::Open()
W "open: $r"
if ($r -ne 'ok') { W "ABORT: 无法打开 Col04 (可能需要管理员)"; exit 1 }

$script:alive = $true
function Live([string]$tag) {
    $l = ''
    $d = [Gx]::Read(0x0000, 16, [ref]$l)      # 已知有效的 16 位读 = 活性探针
    $ok = [bool]$d
    W ("[LV {0}] ok={1}  {2}  :: {3}" -f $tag, $ok, $l, (Hex $d))
    if (-not $ok) { $script:alive = $false }
    return $ok
}

if (-not (Live 'init')) { W "ABORT: IC 初始就不应答，未发送任何新命令"; exit 2 }

# ---- 探针 1：32 位地址读，目标 0x08005000（明文段起点 = 向量表）----
Start-Sleep -Milliseconds 700
$x = ''
$d1 = [Gx]::Read32(0x08005000, 16, [ref]$x)
W ("[P1 READ32 0x08005000 len16] ok={0} {1}" -f [bool]$d1, $x)
if ($d1) { W ("   bytes: " + (Hex $d1)) }

Start-Sleep -Milliseconds 700
if (-not (Live 'after-P1')) { W "ABORT: P1 之后活性丢失，停手"; exit 3 }

if (-not $d1) {
    # ---- 探针 1b：32 位读，目标 0x08000000（flash 起点）----
    Start-Sleep -Milliseconds 700
    $y = ''
    $d1b = [Gx]::Read32(0x08000000, 16, [ref]$y)
    W ("[P1b READ32 0x08000000 len16] ok={0} {1}" -f [bool]$d1b, $y)
    if ($d1b) { W ("   bytes: " + (Hex $d1b)) }
    Start-Sleep -Milliseconds 700
    if (-not (Live 'after-P1b')) { W "ABORT: P1b 之后活性丢失，停手"; exit 3 }
    if (-not $d1b) { W "结论: 32 位地址读不可用（两次均失败）—— 记负结果"; exit 0 }
}

# ---- 探针 2：放大到 64 字节，做逐字节比对 ----
Start-Sleep -Milliseconds 700
$z = ''
$d2 = [Gx]::Read32(0x08005000, 64, [ref]$z)
W ("[P2 READ32 0x08005000 len64] ok={0} {1}" -f [bool]$d2, $z)
if ($d2) { W ("   bytes: " + (Hex $d2)) }

Start-Sleep -Milliseconds 700
Live 'final' | Out-Null

# ---- 比对 ----
$expect = [byte[]](0xC8,0x76,0x00,0x20,0x65,0x51,0x00,0x08,0x79,0xA6,0x00,0x08,0x95,0x88,0x00,0x08)
$got = if ($d1) { $d1 } elseif ($d1b) { $d1b } else { $null }
if ($got) {
    $n = [Math]::Min(16, $got.Length)
    $same = 0
    for ($i = 0; $i -lt $n; $i++) { if ($got[$i] -eq $expect[$i]) { $same++ } }
    W ("[MATCH] 前 {0} 字节中命中 {1} 字节" -f $n, $same)
    if ($same -eq 16) { W "==> ★ 身份确认：设备 0x08005000 处的字节 = 本地明文段头（向量表）" }
    elseif ($same -ge 8) { W "==> 高度疑似同源（部分不符可能是长度截断/偏移差 2），需人工看 hex" }
    else { W "==> 不符：设备该地址的内容与本地镜像无关（记录负结果）" }
}
W "=== done $(Get-Date -Format s) ==="
