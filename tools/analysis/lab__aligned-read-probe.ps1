# aligned-read-probe.ps1 —— 用【起始地址==目标地址】的 4 字节对齐单块读，避开分块伪影
#
# 依据：项目 `追加十一` 同根因记录 —— Gx::Read 分块拼接会产生伪影，
#       必须对每个目标地址单独发起一次、且起始地址与该地址对齐。
#
# 纯读、零写入。每个地址一次 4 字节读，失败即停。

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$LOG = Join-Path $root 'aligned-read-log.txt'
function W($s) { Write-Host $s; Add-Content -LiteralPath $LOG -Value $s -Encoding utf8 }

Add-Type -Path @((Join-Path $root 'ColProbe.cs'), (Join-Path $root 'Gx.cs')) -ErrorAction Stop
W ("=== 对齐单块读探测 :: {0} ===" -f (Get-Date -Format 's'))

$r = [Gx]::Open()
W "Col04 open: $r"
if ($r -ne 'ok') { W "ABORT"; exit 1 }
W ""

# 每个目标地址：单独一次 Read(addr, 4)
function One([int]$addr) {
    $log = ''
    $d = [Gx]::Read($addr, 4, [ref]$log)
    if ($null -eq $d -or $d.Length -lt 4) { return $null }
    return ,$d
}

# 逐目标读：0x4000 区（活性/固件头）、0x452C 区（fw_info）、0x60DC 区（cfg 版本）
$targets = @(
    @(0x4000, 'liveness (项目预期 YELSTO/7869)'),
    @(0x4004, ''),
    @(0x452C, 'fw_info 起点(项目预期)'),
    @(0x4530, ''),
    @(0x4534, ''),
    @(0x4560, ''),
    @(0x4564, ''),
    @(0x60DC, 'cfg 版本(项目预期 1 字节)'),
    @(0x5B2E, '灵敏度相关(项目旧落点)'),
    @(0x96F8, '配置区(项目曾读到结构)'),
    @(0x19000, '配置数据区')
)

W "--- 对齐单块读（每地址独立 4 字节）---"
$ok = 0; $bad = 0
foreach ($t in $targets) {
    $addr = $t[0]; $label = $t[1]
    $d = One $addr
    if ($null -eq $d) {
        W ("  0x{0:X5}  {1,-30} :: <读失败>" -f $addr, $label)
        $bad++
    } else {
        W ("  0x{0:X5}  {1,-30} :: {2}   [{3}]" -f $addr, $label,
            (($d | ForEach-Object { $_.ToString('X2') }) -join ' '),
            (-join ($d | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } })))
        $ok++
    }
    Start-Sleep -Milliseconds 20
}

W ""
W ("成功 {0} / 失败 {1}" -f $ok, $bad)

# 对同一地址连读 4 次，看是否稳定（伪影会表现为每次不同）
W ""
W "--- 稳定性检查：0x452C 连读 4 次 ---"
for ($i = 1; $i -le 4; $i++) {
    $d = One 0x452C
    if ($d) {
        W ("  #{0} :: {1}" -f $i, (($d | ForEach-Object { $_.ToString('X2') }) -join ' '))
    }
    Start-Sleep -Milliseconds 30
}

W ""
W "完成（全程只读，零写入）。"
