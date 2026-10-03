# find-threshold.ps1 —— 用【对齐单块读】在设备 RAM 里搜阈值候选值
#
# 目标：点击阈值实测为 压力 140（按下沿）/ 98（抬起沿）。
#       若设备把阈值存为 16 位值，则会在 RAM 里出现 0x008C / 0x0062。
# 方法：起始地址==目标地址 的 4 字节读（绕开分块伪影），逐个候选地址。
# 输出：命中地址 + 上下文（前后各 8 字节）
#
# 用法：.\find-threshold.ps1 -Start 0x5000 -End 0x6FFF

param(
    [int]$Start = 0x5000,
    [int]$End = 0x6FFF,
    [int]$SleepMs = 0
)

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Add-Type -Path @((Join-Path $here 'ColProbe.cs'), (Join-Path $here 'Gx.cs')) -ErrorAction Stop

$r = [Gx]::Open()
Write-Host "Col04 open: $r"
if ($r -ne 'ok') { exit 1 }

# 要搜的 16 位值（小端字节序）
$targets = @{
    140 = @(0x8C, 0x00)
    98  = @(0x62, 0x00)
    70  = @(0x46, 0x00)
    143 = @(0x8F, 0x00)
}

function ReadBlk([int]$a) {
    $w = ''
    $d = [Gx]::Read($a, 4, [ref]$w)
    if ($d -and $d.Length -ge 4) { return ,$d }
    return $null
}

Write-Host ("扫描 0x{0:X4}..0x{1:X4}（4 字节对齐单块读）" -f $Start, $End)
$hits = @()
$fail = 0
$n = 0
$sw = [System.Diagnostics.Stopwatch]::StartNew()

for ($a = $Start; $a -le $End; $a += 4) {
    $d = ReadBlk $a
    $n++
    if (-not $d) { $fail++; continue }
    # 两个 16 位小端值：d[0..1] 和 d[2..3]
    foreach ($pair in @(@(0, $d[0], $d[1]), @(2, $d[2], $d[3]))) {
        $off = $pair[0]; $lo = $pair[1]; $hi = $pair[2]
        foreach ($k in $targets.Keys) {
            $t = $targets[$k]
            if ($lo -eq $t[0] -and $hi -eq $t[1]) {
                $hits += [pscustomobject]@{
                    Addr = $a + $off
                    Val  = $k
                    Hex  = ('{0:X2} {1:X2}' -f $lo, $hi)
                }
            }
        }
    }
    if ($SleepMs -gt 0) { Start-Sleep -Milliseconds $SleepMs }
}

Write-Host ("读完 {0} 个地址，失败 {1}，用时 {2:N1}s" -f $n, $fail, $sw.Elapsed.TotalSeconds)
Write-Host ""
Write-Host ("命中 {0} 处：" -f $hits.Count)
foreach ($h in $hits) {
    # 取上下文
    $lo = [Math]::Max(0, $h.Addr - 8)
    $ctx = @()
    for ($x = $lo; $x -lt $h.Addr + 12; $x += 4) {
        $d = ReadBlk $x
        if ($d) { $ctx += ('{0:X4}:{1}' -f $x, (($d | ForEach-Object { $_.ToString('X2') }) -join '')) }
    }
    Write-Host ("  0x{0:X4}  = {1} (u16 {2})   ctx: {3}" -f $h.Addr, $h.Hex, $h.Val, ($ctx -join '  '))
}

Write-Host ""
Write-Host "健康确认："
$h14 = ReadBlk 0x4014
$h18 = ReadBlk 0x4018
Write-Host ("  0x4014 = {0}" -f $(if ($h14) { ($h14 | ForEach-Object { $_.ToString('X2') }) -join ' ' } else { '<fail>' }))
Write-Host ("  0x4018 = {0}" -f $(if ($h18) { ($h18 | ForEach-Object { $_.ToString('X2') }) -join ' ' } else { '<fail>' }))
