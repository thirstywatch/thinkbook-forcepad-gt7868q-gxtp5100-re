# verify-fw-identity2.ps1 —— 32 位地址读（多轮续读）+ 阳性对照
#   对照 C: Read32(0x00004000,16)  期望 = mem-scan-16bit.txt 的 0x4000 行 => A7 E0 ED B1 F4 9D CC CC ...
#   探针 1: Read32(0x08000000,16)  期望 = 本地容器明文段头 => C8 76 00 20 65 51 00 08 ...
#   探针 2: Read32(0x08005000,16)  （上一轮此地址返回全零，复测）
# 纪律：单发、前台、间隔 ≥700ms、每次读前后做活性体检、失败即停。只读。
$ErrorActionPreference = 'Continue'
Add-Type -Path @("$PSScriptRoot\ColProbe.cs", "$PSScriptRoot\Gx.cs", "$PSScriptRoot\Gx32.cs") -ErrorAction Stop

$log = Join-Path $PSScriptRoot 'fw-identity-log2.txt'
function W([string]$m) { $m | Out-File -FilePath $log -Append -Encoding utf8; Write-Output $m }
function Hex($d) { if ($d) { ($d | ForEach-Object { $_.ToString('X2') }) -join ' ' } else { '(null)' } }

W "=== fw identity probe #2 start $(Get-Date -Format s) ==="

$r = [Gx32]::Open()
W "open: $r"
if ($r -ne 'ok') { W "ABORT: 无法打开 Col04"; exit 1 }

$script:alive = $true
function LV([string]$tag) {
    $l = ''
    $d = [Gx]::Read(0x0000, 16, [ref]$l)
    $ok = [bool]$d
    W ("[LV {0}] ok={1}  {2}  :: {3}" -f $tag, $ok, $l, (Hex $d))
    if (-not $ok) { $script:alive = $false }
}

LV 'init'
if (-not $script:alive) { W "ABORT: IC 初始不应答"; exit 2 }

function Probe([string]$name, [uint32]$addr, [int]$len) {
    Start-Sleep -Milliseconds 700
    $lg = ''
    $d = [Gx32]::Read32($addr, $len, [ref]$lg)
    W ("[{0} READ32 0x{1:X8} len{2}] ok={3}  {4}" -f $name, $addr, $len, [bool]$d, $lg)
    if ($d) { W ("   bytes: " + (Hex $d)) }
    Start-Sleep -Milliseconds 700
    LV ("after-" + $name)
    if (-not $script:alive) { W "ABORT: 活性丢失，停手"; exit 3 }
    return $d
}

# ---- 对照 ----
$c = Probe 'C-control' 0x00004000 16

# ---- 探针 ----
$p1 = Probe 'P1' 0x08000000 16
$p2 = Probe 'P2' 0x08005000 16

# ---- 比对 ----
$expC = [byte[]](0xA7,0xE0,0xED,0xB1,0xF4,0x9D,0xCC,0xCC,0xD3,0x41,0x71,0xE2,0xE8,0x41,0xDA,0x95)
$expF = [byte[]](0xC8,0x76,0x00,0x20,0x65,0x51,0x00,0x08,0x79,0xA6,0x00,0x08,0x95,0x88,0x00,0x08)

function Cmp([string]$tag, $got, [byte[]]$exp) {
    if (-not $got) { W ("[{0}] 无数据，无法比对" -f $tag); return }
    $n = [Math]::Min(16, $got.Length); $same = 0
    for ($i = 0; $i -lt $n; $i++) { if ($got[$i] -eq $exp[$i]) { $same++ } }
    W ("[{0}] 前 {1} 字节命中 {2}" -f $tag, $n, $same)
}

Cmp 'CONTROL(0x4000)' $c $expC
Cmp 'FLASH(0x08000000)' $p1 $expF
Cmp 'FLASH(0x08005000)' $p2 $expF

W "=== done $(Get-Date -Format s) ==="
